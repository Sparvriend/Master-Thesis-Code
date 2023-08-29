import argparse
import json
import os
import re
import time

EX_PATH = "Experiments"


def experiment_1():
    """Experiment 1: Synthetic data study on the NTZFilter Dataset.
    Experiment 1a: Adding synthetic data in different proportions to
    the training set. Only concerns ResNet18 and MobileNetV2.
    Experiment 1b: Training on only synthetic data, validating on real set.
    Experiment 1c: Training on only real data, validating on synthetic set.
    Both experiment 1b and 1c include feature analysis with IG.
    TODO: SHOULD EXPERIMENT 1A BE REMOVED?
    TODO: What is the optimal NTZFilterSyntheticDataset?
    """
    classifiers = ["mobilenet_v2(weights = MobileNet_V2_Weights.DEFAULT)",
                   "resnet18(weights = ResNet18_Weights.DEFAULT)"]
    n_runs = 1

    # Experiment 1a
    # In experiment 1a, the total size of the dataset is always 48.
    combs = [[12, 0.25], [24, 0.5], [36, 0.75], [48, 1]]
    for comb in combs:
        train_set = comb[0]
        train_ratio = comb[1] 
        for classifier in classifiers:
            # Editing JSON file, creating synthetic data and running experiment
            ex_name = edit_json("experiment_1", ["model"],
                                [classifier, train_set, train_ratio])
            os.system("python3.10 synthetic_data.py " + str(train_set)
                      + " " + str(train_ratio) + " 0 0")
            os.system("python3.10 train.py " + ex_name.replace(".json", "")
                      + " --n_runs " + str(n_runs))
            delete_json(ex_name)

    # Experiment 1b/1c
    # In experiment 1b/1c, the size of the dataset can be larger than 48.
    combs = [[200, 1, 0, 0], [0, 0, 48, 1]]
    for comb in combs:
        train_set = comb[0]
        train_ratio = comb[1]
        val_set = comb[2]
        val_ratio = comb[3]
        for classifier in classifiers:
            # Editing JSON file, creating synthetic data and running experiment
            ex_name = edit_json("experiment_1", ["model"], [classifier, train_set,
                                                            train_ratio, val_set,
                                                            val_ratio])
            os.system("python3.10 synthetic_data.py " + str(train_set)
                                                      + " " + str(train_ratio)
                                                      + " " + str(val_set)
                                                      + " " + str(val_ratio))
            os.system("python3.10 train.py " + ex_name.replace(".json", "")
                      + " --n_runs " + str(n_runs))
            # Running integrated gradients with the results directory
            directory = find_directory(ex_name.replace(".json", ""))
            os.system("python3.10 explainability.py " + directory + " Captum")
            delete_json(ex_name)


def experiment_2():
    """Experiment 2: Augmentation testing per classifier
    on the NTZFilterSynthetic dataset.
    # TODO: Random apply is terribly slow and is not useful anyway, remove???
    """
    classifiers = ["mobilenet_v2(weights = MobileNet_V2_Weights.DEFAULT)",
                   "resnet18(weights = ResNet18_Weights.DEFAULT)",
                   "shufflenet_v2_x1_0(weights = ShuffleNet_V2_X1_0_Weights.DEFAULT)",
                   "efficientnet_b1(weights = EfficientNet_B1_Weights.DEFAULT)"]
    augmentations = ["rand_augment", "categorical", "random_choice", 
                     "auto_augment", "random_apply"]
    n_runs = 1
    
    # Create the dataset to run the experiment on
    os.system("python3.10 synthetic_data.py 200 0 20 0 --no_combine")

    for classifier in classifiers:
        for augment in augmentations:
            # Edit the JSON file, call the experiment and delete the JSON
            ex_name = edit_json("experiment_2", ["model", "augmentation"],
                                [classifier, augment])
            os.system("python3.10 train.py " + ex_name.replace(".json", "")
                      + " --n_runs " + str(n_runs))
            delete_json(ex_name)


def experiment_3():
    """Experiment 3: Classifier testing on the NTZFilterSynthetic dataset.
    Includes the best augmentation techniques from experiment 2.
    Includes a feature analsysis with IG.
    TRT vs. no TRT speeds have to be run manually.
    GFLOPS calculation has to be run manually.
    # TODO: FILL IN BEST AUGMENTATION PER CLASSIFIER FROM EXPERIMENT 2.
    """
    combs = [["mobilenet_v2(weights = MobileNet_V2_Weights.DEFAULT)",
              "rand_augment"],
             ["resnet18(weights = ResNet18_Weights.DEFAULT)",
              "rand_augment"],
             ["shufflenet_v2_x1_0(weights = ShuffleNet_V2_X1_0_Weights.DEFAULT)",
              "rand_augment"],
             ["efficientnet_b1(weights = EfficientNet_B1_Weights.DEFAULT)",
              "rand_augment"]]
    n_runs = 1
    
    # Create the dataset to run the experiment on
    os.system("python3.10 synthetic_data.py 200 0 20 0 --no_combine")

    for comb in combs:
        classifier = comb[0]
        augment = comb[1]

        # Edit the JSON, run the experiment, run IG and delete JSON
        ex_name = edit_json("experiment_3", ["model", "augmentation"],
                            [classifier, augment])
        ex_name_rm = ex_name.replace(".json", "")
        os.system("python3.10 train.py " + ex_name_rm
                  + " --n_runs " + str(n_runs))
        directory = find_directory(ex_name_rm)
        os.system("python3.10 explainability.py " + directory + " Captum")
        delete_json(ex_name)


def experiment_4():
    """Experiment 4: DUQ analysis on CIFAR10 dataset.
    Experiment 4a: Classifier performance when DUQ converted with GP.
    Experiment 4b: Classifier performance when DUQ converted without GP.
    TODO: IS THIS EXPERIMENT EVEN NECESSARY?
    """
    combs = [["mobilenet_v2()", ["0.1", "0"]],
             ["resnet18()", ["0.5", "0"]],
             ["shufflenet_v2_x1_0()", ["0.1", "0"]],
             ["efficientnet_b1()", ["0.1", "0"]]]
    n_runs = 1

    for comb in combs:
        classifier = comb[0]
        for gp in comb[1]:
            # Edit the JSON file, call the experiment and delete the JSON
            ex_name = edit_json("experiment_4", ["model", "gp_const"],
                                [classifier, gp])
            os.system("python3.10 train_rbf.py " + ex_name.replace(".json", "")
                      + " --n_runs " + str(n_runs))
            delete_json(ex_name)


def experiment_5():
    """Experiment 5: DUQ analysis on NTZFilter dataset.
    Includes feature analysis with IG on a DUQ model.
    Model speeds have to be run manually (No TRT).
    TODO: SHOULD AUGMENTATIONS FROM EXPERIMENT 2 BE USED HERE?
    """
    
    combs = [["mobilenet_v2()", "lr = 0.05"],
             ["resnet18()", "lr = 0.01"],
             ["shufflenet_v2_x1_0()", "lr = 0.05"],
             ["efficientnet_b1()", "lr = 0.01"]]
    n_runs = 1

    # Create the dataset to run the experiment on
    os.system("python3.10 synthetic_data.py 200 0 20 0 --no_combine")
    
    for comb in combs:
        classifier = comb[0]
        lr = comb[1]

        # Editing JSON, running experiment, running IG and deleting JSON.
        ex_name = edit_json(experiment_5, ["model"], [classifier, lr])
        ex_name_rm = ex_name.replace(".json", "")
        os.system("python3.10 train_rbf.py " + ex_name_rm +
                  " --n_runs " + str(n_runs))
        directory = find_directory(ex_name_rm)
        os.system("python3.10 explainability.py " + directory + " Captum")
        delete_json(ex_name)


def experiment_6():
    # TODO: Code this experiment 
    print("Coming soon...")
    # Experiment 6: (Perhaps omit this as well?) Edge case analysis.
    # Experiment 6a: Give a DUQ model a sample that is from a completely
    # different dataset (out of distribution), see what uncertainty is given.
    # Experiment 6b: Add noise to a testing image, see what uncertainty is given.


def delete_json(json_name: str):
    """Function that deletes a JSON file.

    Args:
        json_name: Name of the JSON file to delete.
    """
    try:
        os.remove(os.path.join(EX_PATH, json_name))
        print(f"{json_name} has been deleted.")
    except FileNotFoundError:
        print(f"{json_name} does not exist.")


def edit_json(json_name, json_args, json_values):
    """Function that takes a basic JSON file for an experiment,
    edits it and saves that new version.

    Args:
        json_name: Name of the JSON file to edit.
        json_args: List of arguments to edit.
        json_values: List of values to edit the arguments to.
    Returns:
        Name of the experiment results folder.
    """

    with open(os.path.join(EX_PATH, json_name + ".json")) as ex_file:
        data = json.load(ex_file)

    for arg, value in zip(json_args, json_values):
        data[arg] = value
    if json_name == "experiment_5":
        optimizer = data["optimizer"]
        data["optimizer"] = optimizer.replace("lr = 0.05", json_values[1])

    ex_name = json_name
    for value in json_values:
        ex_name += "_" + str(value)
    ex_name += ".json"
    re_pattern = r'\(.*\)'
    ex_name = re.sub(re_pattern, '', ex_name)

    with open(os.path.join(EX_PATH, ex_name), 'w') as temp_file:
        json.dump(data, temp_file)

    return ex_name


def find_directory(ex_name):
    """Function that finds the directory of the experiment results.

    Args:
        ex_name: Name of the experiment results folder.
    Returns:
        Name of the experiments results folder, but including
        the timestamp.
    """

    # Since the folder is saved with a timestamp, to run IG
    # it has to be selected first
    all_directories = os.listdir(os.path.join("Results", "Experiment-Results"))
    for directory in all_directories:
        if directory.startswith(ex_name):
            break
    return directory


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("experiment", type = str)
    args = parser.parse_args()
    start = time.time()

    if args.experiment == "experiment_1":
        # Time estimate (no new synthetic data): 13 minutes
        experiment_1()
    elif args.experiment == "experiment_2":
        # Time estimate (no new synthetic data): 75 minutes
        experiment_2()
    elif args.experiment == "experiment_3":
        experiment_3()
    elif args.experiment == "experiment_4":
        experiment_4()
    elif args.experiment == "experiment_5":
        experiment_5()
    elif args.experiment == "experiment_6":
        experiment_6()
    
    elapsed_time = time.time() - start
    print("Total training time for " + args.experiment + " (H/M/S) = ", 
          time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))