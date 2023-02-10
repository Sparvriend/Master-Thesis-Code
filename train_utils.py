import torch
import os

TEST_PATH_NO_LABEL = "data/test_no_label"

# Function that converts labels to a list and then saves paths and labels to a txt file
def save_test_predicts(predicted_labels, paths):
    # Converting predicted labels to a list
    predicted_labels = predicted_labels.flatten(); predicted_labels = predicted_labels.tolist()

    file = open(os.path.join(TEST_PATH_NO_LABEL, "test_predicts.txt"), "a")
    for i in range(len(predicted_labels)):
        file.write(paths[i] + " " + str(predicted_labels[i]) + "\n")

# Manual replacement of default collate function provided by PyTorch
# The function removes the augmentation and the path that is normally returned by using __getitem__ as well as transforming to lists of tensors
def sep_collate(batch):
    _, images, labels, _ = zip(*batch)
    tensor_labels = []

    # Labels are ints, which is why they need to be converted to tensors before being entered into a torch stack
    for label in labels:
        tensor_labels.append(torch.tensor(label))

    # Converting both images and label lists of tensors to torch stacks
    images = torch.stack(list(images), dim = 0)
    labels = torch.stack(list(tensor_labels), dim = 0)

    return images, labels

# Manual collate function for testing dataloader
def sep_test_collate(batch):
    path, images, _, _ = zip(*batch)

    # Converting image lists of tensors to torch stack
    images = torch.stack(list(images), dim = 0)

    return images, path