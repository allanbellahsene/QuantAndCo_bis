import os

import pandas   as pd
import pylab    as pl

from joblib import dump, load

from sklearn.ensemble           import RandomForestClassifier
from sklearn.model_selection    import train_test_split

from sklearn.metrics import confusion_matrix, roc_curve, roc_auc_score, accuracy_score, precision_score, recall_score

from DataPipeline.get_data  import get_ml_bars_data

def make_model_name(target, symbol, date_test, thres, n_poinst):
    if not isinstance(date_test, str):
        date_test   = date_test.strftime('%Y-%m-%d-%H-%M-%S')
    
    return f"rf_classifier_{target}_{symbol}_{date_test}_thres={thres}_n={n_poinst}"

def get_model_path(model_name):
    return f"Model/{model_name}.joblib"

def get_model(target, symbol, date_test, thres, n_poinst):
    model_name  = make_model_name(target, symbol, date_test, thres, n_poinst)
    
    return load(get_model_path(model_name))

def train_rf(X, Y, model_name, n_jobs=5, to_load=False):
    # Check if the model has already been trained
    model_path  = get_model_path(model_name)
    if os.path.exists(model_path) and to_load:
        # Load the existing model
        clf = load(model_path)
        print("Model loaded from file.")
    else:
        clf = RandomForestClassifier(n_estimators=1000, random_state=42, max_depth=5, n_jobs=n_jobs)
    
    X_train, X_val, Y_train, Y_val  = train_test_split(X, Y, train_size=0.75, shuffle=True)
    # Create and train a new model
    clf.fit(X_train, Y_train)
    # Save the trained model to a file
    dump(clf, model_path)
    print("New model trained and saved.")

    evaluate_model(clf, X_val, Y_val, model_name, "validation")

    return clf

def evaluate_model(model, X, Y, model_name, data_type):
    # Predict the responses for the given dataset
    Y_pred = model.predict(X)
    
    # Calculate the confusion matrix
    tn, fp, fn, tp  = confusion_matrix(Y, Y_pred).ravel()
    
    # Calculate additional metrics
    accuracy        = accuracy_score(Y, Y_pred)
    precision       = precision_score(Y, Y_pred)
    recall          = recall_score(Y, Y_pred)
    fpr, tpr, _     = roc_curve(Y, model.predict_proba(X)[:, 1])
    auc = roc_auc_score(Y, model.predict_proba(X)[:, 1])
    
    score       = pd.DataFrame({l: [d] for l, d in zip(
                                                    ["TN", "FP", "FN", "TP", "Accuracy", "Precision", "Recall", "AUC", "model", "data"],
                                                    [tn, fp, fn, tp, accuracy, precision, recall, auc, model_name, data_type]
                                                    )
                                }
                            )
    
    file_score  = f"Score/classiers.csv"
    if not os.path.exists(file_score):
        score.to_csv(file_score, index=False)
    else:
        score.to_csv(file_score, index=False, header=False, mode="a")

    # Print the evaluation metrics
    print(f"{model_name} {data_type} set metrics:")
    print(f"True Positives: {tp}, False Positives: {fp}")
    print(f"True Negatives: {tn}, False Negatives: {fn}")
    print(f"Accuracy: {accuracy:.2f}")
    print(f"Precision: {precision:.2f}")
    print(f"Recall (TPR): {recall:.2f}")
    print(f"AUC: {auc:.2f}")
    
    # Plot ROC curve (optional)
    pl.figure(size=(8,6))
    pl.plot(fpr, tpr, label=f'{model_name} {data_type} set (AUC = {auc:.2f})')
    pl.plot([0, 1], [0, 1], 'k--')  # Dashed diagonal
    pl.xlabel('False Positive Rate')
    pl.ylabel('True Positive Rate')
    pl.title(f'ROC Curve ({model_name} {data_type} set)')
    pl.grid()
    pl.savefig(f"Figure/RF_classifier/{model_name}_{data_type}.png")

def train_take_profit_classifiers(date_start, date_end, date_test, symbol, interval, thres=1., n_points=60, to_load=False):
    data, hits, bar = get_ml_bars_data(symbol, interval, date_start, date_end, thres=thres, n_points=n_points)

    n_hit, n_take, hit, take    = len(hits[hits==1]), len(bar[bar==1]), len(hits), len(bar)

    print(len(data))
    print(len(hits), len(hits[hits==1]), len(hits[hits==0]))
    print(len(bar), len(bar[bar==1]), len(bar[bar==0]))

    if n_hit >= 0.1*hit and n_take >= 0.3*take and n_take <= 0.7*take:
        data_test, hits_test, bar_test      = data[data.index > date_test], hits[hits.index > date_test], bar[bar.index > date_test]
        data_train, hits_train, bar_train   = data[data.index <= date_test], hits[hits.index <= date_test], bar[bar.index <= date_test]

        date_test       = date_test.strftime('%Y-%m-%d-%H-%M-%S')
        direction_name  = make_model_name("direction", symbol, date_test, thres, n_points)
        hitting_name    = make_model_name("hitting", symbol, date_test, thres, n_points)

        model_direction = train_rf(data_train.loc[bar_train.index].to_numpy(), bar_train.to_numpy(), direction_name, to_load=to_load)
        model_hitting   = train_rf(data_train.loc[hits_train.index].to_numpy(), hits_train.to_numpy(), hitting_name, to_load=to_load)

        evaluate_model(model_direction, data_test.loc[bar_test.index].to_numpy(), bar_test.to_numpy(), direction_name, "test")
        evaluate_model(model_hitting, data_test.loc[hits_test.index].to_numpy(), hits_test.to_numpy(), hitting_name, "test")
    else:
        print("Not Enough Heterogeneity in the target")

if __name__ == "__main__":
    date1       = "2021-04-05-23:44:12"
    date2       = "2024-04-04-23:44:12"
    date_test   = pd.to_datetime("2024-01-01 00:00:00")

    symbol      = 'BTCUSDT'
    interval    = ['1m', '1h', '1d', '1w']

    thres       = [0.5, 0.8, 1., 1.2, 1.5, 1.8, 2., 2.5, 3.]
    n_points    = [20, 40, 60, 100, 200, 400, 600]
    for th in thres:
        for n in n_points:
            print(f"Start thres={th} n={n}")
            train_take_profit_classifiers(date1, date2, date_test, symbol, interval, thres=th, n_points=n, to_load=False)
            print("Finish")
            print()
