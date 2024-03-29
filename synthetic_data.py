import argparse
import cv2
import numpy as np
import os
import random
import shutil
import time
import torchvision.transforms as T

from PIL import Image


# Path definitions:
TEMPLATE_PATH = os.path.join("raw_data", "synthetic_samples", "templates")
BACKGROUNDS_PATH = os.path.join("raw_data","synthetic_samples", "background")
CLASS_LABELS_PATH = os.path.join("raw_data", "NTZ_filter_synthetic", "class_labels")
FILTER_SELECTED_PATH = os.path.join("raw_data", "NTZ_filter_synthetic", "filter_selected")
FILTER_REMOVED_PATH = os.path.join("raw_data", "NTZ_filter_synthetic", "label_removed")
SYNTHETIC_EX_PATH = os.path.join("raw_data", "NTZ_filter_synthetic", "synthetic_data")


def create_synthetic_data_dirs(class_names: list):
    """Function that creates all directories required for synthetic
    data generation and saving progress of intermediate steps.

    Args:
        class_names: List of class names.
    """
    # Creating top level directory
    path = os.path.join("raw_data", "NTZ_filter_synthetic")
    if not os.path.exists(path):
        os.mkdir(path)

        # Creating directories for saving intermediate phases
        # class_labels and synthetic_data_ex have class subdirectories
        dirlist = [CLASS_LABELS_PATH, FILTER_SELECTED_PATH, 
                   FILTER_REMOVED_PATH, SYNTHETIC_EX_PATH]
        for dir in dirlist:
            os.mkdir(dir)

        # Lisiting and creating class directories for class_labels
        for class_name in class_names:
            dir_path = os.path.join(CLASS_LABELS_PATH, class_name)
            os.mkdir(dir_path)
            dir_path = os.path.join(SYNTHETIC_EX_PATH, class_name)
            os.mkdir(dir_path)

            
def get_removed_label(class_names: list, data_types: list):
    """Function that does two primary things: 1. Matching the class template
    to the class label in the image (get_template_match), saving that
    template to the class_labels directory. 2. Removing the class label
    from the image, by filling in the pixels in the bounding box that fall
    over a certain insensity threshold (remove_and_fill).

    Args:
        class_names: List of class names
        data_types: List of data types (train, val, test)
    """
    # Iterating over all images usable for data generation
    for data_type in data_types:
        for class_name in class_names:
            class_path = os.path.join("data", "NTZFilter", data_type, class_name)
            files = os.listdir(class_path)
            template = Image.open(os.path.join(TEMPLATE_PATH, class_name + "_template.png"))
            for file in files:
                img = Image.open(os.path.join(class_path, file))

                # Matching each file to the class template
                top_left, bottom_right = get_template_match(img, template)
                # Cropping and saving the resulting bounding box with the label
                label_box = img.crop((top_left[0], top_left[1], bottom_right[0], bottom_right[1]))

                x_range = list(range(label_box.size[0]))
                y_range = list(range(label_box.size[1]))
                label_pixels = check_incorrect_match(x_range, y_range, label_box, lambda x: x < 220)

                # If not within this range, template matching failed
                if label_pixels < 3000 and label_pixels > 1000:
                    label_box.save(os.path.join(CLASS_LABELS_PATH, class_name, file))

                    # Only taking filters from fail_label_not_fully_printed and no_fail
                    # Since the other classes have unstable inpainting
                    if class_name == "fail_label_not_fully_printed" or class_name == "no_fail":
                        # Removing the label from the image and filling up with background
                        img = remove_and_fill(img, top_left, bottom_right)

                        # Saving the resulting image
                        img_destination = os.path.join(FILTER_REMOVED_PATH, file)
                        img.save(img_destination)


def get_selected_filter() -> dict:
    """This function takes all filters with their labels removed from them
    applies normalized pattern matching to each filter to see where in the image
    the filter is located. A subset of those filters is then saved as a filter image
    in the filters_selected directory. Cylinder and filter templates are split up
    and cylinder templates are matched multiple times to get the best result.

    Returns:
        A dictionary with the filter name as key and the top left and bottom right
        coordinates of the filter as value.
    """
    files = os.listdir(FILTER_REMOVED_PATH)
    cutoff_template = Image.open(os.path.join(TEMPLATE_PATH, "filter_cutoff_template.png"))
    succes_count = 0
    filter_coordinates = {}

    # Create cylinder template list
    cylinder_templates = ["filter_cylinder_template_r.png", "filter_cylinder_template_l1.png",
                          "filter_cylinder_template_l2.png"]

    for file in files:
        img = Image.open(os.path.join(FILTER_REMOVED_PATH, file))

        # The cutoff template is almost always (at least partially) correct
        top_left_f, bottom_right_f = get_template_match(img, cutoff_template)

        # It can sometimes happen that the label on the filter is removed
        # incorrectly in get_removed_label, but those are often not selected
        # anyway in this procedure, if in the future that changes, see old commits
        # for a method on how to solve that.

        for cylinder_template_name in cylinder_templates:
            cylinder_template = Image.open(os.path.join(TEMPLATE_PATH, cylinder_template_name))
            top_left_c, bottom_right_c = get_template_match(img, cylinder_template)

            x_range = list(range(bottom_right_c[0] - top_left_c[0]))
            y_range = list(range(bottom_right_c[1] - top_left_c[1]))

            # Checking for an incorrect match
            cylinder_pixels = check_incorrect_match(x_range, y_range, img, lambda x: x < 60, top_left_c)

            if cylinder_pixels > 200:
                # If the match is accurate, combine the two rectangles
                top_left_cc = (min(top_left_f[0], top_left_c[0]), min(top_left_f[1], top_left_c[1]))
                bottom_right_cc = (max(bottom_right_f[0], bottom_right_c[0]), max(bottom_right_f[1], bottom_right_c[1]))

                # Creating a new image to draw the two rectangles on
                width = bottom_right_cc[0] - top_left_cc[0]
                height = bottom_right_cc[1] - top_left_cc[1]
                combined = Image.new('RGB', (width, height), (0, 0, 0))

                # Filter image crop and paste
                area_f = img.crop((top_left_f[0], top_left_f[1], bottom_right_f[0], bottom_right_f[1]))
                combined.paste(area_f, (top_left_f[0] - top_left_cc[0], top_left_f[1] - top_left_cc[1]))

                # Black cylinder image crop and paste
                area_c = img.crop((top_left_c[0], top_left_c[1], bottom_right_c[0], bottom_right_c[1]))
                combined.paste(area_c, (top_left_c[0] - top_left_cc[0], top_left_c[1] - top_left_cc[1]))

                # Add in the space between the two template matches, if it is not connected
                # This is the cylinder template on the right side case
                if top_left_f[0] != 0 and bottom_right_f[0] != top_left_c[0]:
                    top_left_i = (bottom_right_f[0], top_left_c[1])
                    bottom_right_i = (top_left_c[0], bottom_right_c[1])
                    area_i = img.crop((top_left_i[0], top_left_i[1], bottom_right_i[0], bottom_right_i[1]))
                    combined.paste(area_i, (top_left_i[0] - top_left_cc[0], top_left_i[1] - top_left_cc[1]))

                # Cylinder template on the left side case
                if bottom_right_f[0] != 0 and top_left_f[0] != bottom_right_c[0]:
                    top_left_i = (bottom_right_c[0], top_left_c[1])
                    bottom_right_i = (top_left_f[0], bottom_right_c[1])
                    area_i = img.crop((top_left_i[0], top_left_i[1], bottom_right_i[0], bottom_right_i[1]))
                    combined.paste(area_i, (top_left_i[0] - top_left_cc[0], top_left_i[1] - top_left_cc[1]))

                # Perform a final check to remove incorrect template matches
                x_range = list(range(width))
                y_range = list(range(height))
                black_pixels = check_incorrect_match(x_range, y_range, combined, lambda x: x < 1)
                if black_pixels < 1500:
                    succes_count += 1
                    name = file + ".bmp"
                    filter_coordinates[name] = (top_left_f, bottom_right_f)
                    combined.save(os.path.join(FILTER_SELECTED_PATH, name))
                    break

    print("Succesful template matches = " + str(succes_count) + "/" + str(len(files)))
    return filter_coordinates


def generate_synthetic_data(filter_coordinates: dict, class_names: list, n_data: int):
    """Function that takes filter images from FILTER_SELECTED_PATH and takes labels
    from CLASS_LABELS_PATH and pastes them on the filter images. The resulting image
    is then painted on a background image.
    
    Args:
        filter_coordinates: Dictionary with confines the labels should be printed in.
        class_names: List of class names.
        n_data: Number of data points to generate per class.
    """
    # Getting a list of all filter images and subsetting
    all_filters = os.listdir(FILTER_SELECTED_PATH)
    subset_filters = np.random.choice(all_filters, size = n_data * len(class_names))
    backgrounds = os.listdir(BACKGROUNDS_PATH)
    
    for i, class_name in enumerate(class_names):
        class_labels = os.listdir(os.path.join(CLASS_LABELS_PATH, class_name))
        subset_class_labels = np.random.choice(class_labels, size = n_data)
        for j, class_label in enumerate(subset_class_labels):
            # Paste the class label randomly somewhere on the filter
            # But restricted, such that it does fall in the right area
            filter_name = subset_filters[i*len(class_names)+j]
            filter_img = Image.open(os.path.join(FILTER_SELECTED_PATH, filter_name))
            class_label_img = Image.open(os.path.join(CLASS_LABELS_PATH,
                                                      class_name, class_label)) 

            # The filter_img should be converted to a version that does not 
            # contain black pixels by appending the cylinder part
            filter_mask = find_mask(filter_img, lambda x: x != 0)
            
            # Randomly selecting label on filter location
            w_label, h_label = class_label_img.size
            top_left, bottom_right = filter_coordinates[filter_name]
            w_filter = bottom_right[0] - top_left[0]
            h_filter = bottom_right[1]  - top_left[1] 
            pix_to_edge = 15

            # Since the half printed label is always on the left, print it on the left
            if class_name == "fail_label_half_printed":
                x = filter_img.size[0] - w_filter
            else:
                x = random.randint(pix_to_edge, w_filter - w_label - pix_to_edge)
            y = random.randint(pix_to_edge, h_filter - h_label - pix_to_edge)

            # Applying random rotation and random horizontal flip transformation
            # Then pasting on the filter
            transform = T.Compose([T.RandomChoice([T.RandomRotation(degrees = (0, 10)),
                                                   T.Lambda(lambda x: x)]),
                                   T.RandomHorizontalFlip(p = 0.25)])
            class_label_img = transform(class_label_img)

            # Converting the class_label_img to a version that only has
            # pixels for the label and pasting only that part
            class_label_mask = find_mask(class_label_img, lambda x: x < 220 and x > 120)
            filter_img = paste_selected(filter_img, class_label_img, class_label_mask, x, y)
            
            # Post processing step of inpainting the edges of the class label img
            if class_name != "fail_label_half_printed":
                filter_img = paint_rect_edges(filter_img, (x, y),
                                (x + class_label_img.size[0], y + class_label_img.size[1]),
                                edge_width = 3, radius = 4)
            else:
                filter_img = paint_rect_edges(filter_img, (x, y),
                                (x + class_label_img.size[0], y + class_label_img.size[1]),
                                edge_width = 3, radius = 2)

            # Then paste the filter img randomly somewhere on the background
            # Ensuring that the top 60 pixels and bottom 30 pixels are not
            # possible, since the edge of the filter system is there
            background_img = Image.open(os.path.join(BACKGROUNDS_PATH,
                                                     random.choice(backgrounds)))
            w_background, h_background = background_img.size
            # w_filter is the size of the filter, without the cylinder,
            # but here the cylinder should be added to the width
            w_filter = filter_img.size[0]
            h_filter = filter_img.size[1]
            x = random.randint(0, w_background - w_filter)
            y = random.randint(60, h_background - h_filter - 30)

            # Pasting filter with label, applying post-processing and saving
            background_img = paste_selected(background_img, filter_img, filter_mask, x, y)
            background_img = paint_rect_edges(background_img, (x, y),
                             (x + filter_img.size[0], y + filter_img.size[1]),
                             edge_width = 8, radius = 20)
            background_img.save(os.path.join(SYNTHETIC_EX_PATH, class_name,
                                             "example_" + str(i*len(class_names) + j) + "_" + class_name + ".png"))


def get_template_match(img: Image.Image, template: Image.Image) -> tuple[tuple, tuple]:
    """This is a function that takes in an image and a template.
    It looks for the closest match of the template in the image.
    The image is normalized such that the template does not have to
    exactly match the image.

    Args:
        img: PIL image
        template: PIL image of template available in img

    Returns:
        Two tuples of (x, y) coordinates of the top left and bottom right
        bounding box coordinates.
    """
    # Converting image and template to greyscale since its easier to work with
    grey_img = np.array(img.convert("L"))
    grey_template = np.array(template.convert("L"))

    # Computing the mean and standard deviation of the template
    # and normalizing template
    mean = np.mean(grey_template)
    std_dev = np.std(grey_template)
    normalized_template = (grey_template - mean) / std_dev

    # Getting grey_template shape
    w, h = grey_template.shape
    
    # Computing the size of the resulting match
    # and initializing match array
    match_shape = (grey_img.shape[0] - w + 1,
                   grey_img.shape[1] - h + 1)
    match = np.zeros(match_shape)

    # Computing the cross-correlation between the template and the image
    for y in range(match_shape[0]):
        for x in range(match_shape[1]):
            # Getting patch from image
            patch = grey_img[y:y + w, x:x + h]

            # Computing mean and standard deviation of patch
            patch_mean = np.mean(patch)
            patch_std_dev = np.std(patch)

            # Computing normalized patch and cross-correlation
            normalized_patch = (patch - patch_mean) / patch_std_dev
            match[y, x] = np.sum(normalized_patch * normalized_template)

    # Find the location with the highest cross-correlation
    x, y = np.unravel_index(np.argmax(match), match_shape)
    top_left = (y, x)
    bottom_right = (y + h, x + w)
    return top_left, bottom_right


def remove_and_fill(img: Image.Image, top_left: tuple, bottom_right: tuple) -> Image.Image:
    """Function that takes a bounding box in an image
    and based on pixel intensity criteria, removes pixels
    thought to be label pixels.

    Args:
        img: PIL image
        top_left: Tuple of (x, y) coordinates of top left corner of bounding box.
        bottom_right: Tuple of (x, y) coordinates of bottom right corner of bounding box.

    Returns:
        An image with label pixels removed in the bounding box.
    """
    # Converting to greyscale and CV2 image, since its required for inpainting
    img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    grey_image = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # x and y range of the bounding box
    x_range = list(range(bottom_right[0] - top_left[0]))
    y_range = list(range(bottom_right[1] - top_left[1]))
    
    # Creating initially empty mask
    mask = np.zeros((img.shape[0], img.shape[1]), dtype = np.uint8)

    # Iterating over all pixels in the bounding box
    # Any pixel that is not very white is likely to be a label print
    for x in x_range:
        for y in y_range:
            point_x = top_left[0] + x
            point_y = top_left[1] + y
            if grey_image[point_y, point_x] < 250:
                # The pixel is likely a label print pixel
                mask[point_y, point_x] = 1

    # Using inpainting to remove label print
    # From OpenCV library, since it does not exist in PIL
    img_label_removed = cv2.inpaint(img, mask, 2, cv2.INPAINT_NS)
    # And converting back to PIL
    img_label_removed = Image.fromarray(cv2.cvtColor(img_label_removed,
                                                     cv2.COLOR_BGR2RGB))
    return img_label_removed


def paint_rect_edges(img: Image.Image, top_left: tuple, bottom_right: tuple,
                     edge_width: int, radius: int) -> Image.Image:
    """This function takes a PIL image, converts to cv2, creates a mask,
    fills the mask with a rectangle based on top_left and bottom_right
    based on an edge_width. CV2's inpainting function is then used to
    normalize these mask pixels by comparing to nearest pixels within radius.

    Args:
        img: PIL image
        top_left: Tuple of (x, y) coordinates of top left corner of bounding box.
        bottom_right: Tuple of (x, y) coordinates of bottom right corner of bounding box.
        edge_width: Width of the edges of the rectangle to be filled.
        radius: Radius of the inpainting function.
    Returns:
        A PIL image with the edges of the rectangle filled.
    """
    # Converting to CV2, create mask and do inpainting
    img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    mask = np.zeros((img.shape[0], img.shape[1]), dtype = np.uint8)
    x1, y1 = top_left
    x2, y2 = bottom_right
    
    # Checking if the mask goes out of bounds with added edge width
    if x1 - edge_width < 0:
        x1 = 0
    if y1 - edge_width < 0:
        y1 = 0
    if x2 + edge_width > img.shape[1]:
        x2 = img.shape[1] - 1
    if y2 + edge_width > img.shape[0]:
        y2 = img.shape[0] - 1

    # Creating mask
    mask[y1 - edge_width:y1, x1 - edge_width:x2 + edge_width+1] = 1
    mask[y2 + 1:y2 + 1 + edge_width, x1 - edge_width:x2 + edge_width + 1] = 1
    mask[y1:y2 + 1, x1 - edge_width:x1] = 1
    mask[y1:y2 + 1, x2 + 1:x2 + 1 + edge_width] = 1
    img = cv2.inpaint(img, mask, radius, cv2.INPAINT_NS)

    # And converting back to PIL
    img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    return img


def check_incorrect_match(x_range: list, y_range: list, img: Image.Image,
                          condition, top_left = [0,0]) -> int:
    """Function that checks a condition for an image to see how many
    pixels in the image meet that condition.
    
    Args:
        x_range: List of x coordinates to check.
        y_range: List of y coordinates to check.
        img: PIL image.
        condition: Function that takes a pixel value and returns a boolean.
        top_left: Tuple of (x, y) coordinates of top left corner of bounding box.
    Returns:
        Number of pixels that meet the condition.
    """
    # Working with a grey image to check the intensity
    img = img.convert("L")
    pixels = 0
    # Looping over pixels
    for x in x_range:
        for y in y_range:
            if condition(img.getpixel((x + top_left[0], y + top_left[1]))):
                pixels += 1
    return pixels


def paste_selected(background_img: Image.Image, paste_img: Image.Image,
                   mask_img: Image.Image, x_offset: int, y_offset: int) -> Image.Image:
    """Function that takes a background image and an image to paste on it
    any pixel is painted on the background image, if the mask value is 1.
    
    Args:
        background_img: PIL image.
        paste_img: PIL image.
        mask_img: PIL image.
        x_offset: Offset in x direction.
        y_offset: Offset in y direction.
    Returns:
        A PIL image with the paste_img pasted on it.
    """
    for y in range(mask_img.size[1]):
        for x in range(mask_img.size[0]):
            if mask_img.getpixel((x, y)) == 1:
                pixel = paste_img.getpixel((x, y))
                background_img.putpixel((x + x_offset, y + y_offset), pixel)
    return background_img


def find_mask(img: Image.Image, condition) -> Image.Image:
    """Function that takes a PIL image and a condition and returns
    a mask in which every pixel that meets the condition has a value
    of 1.
    
    Args:
        img: PIL image.
        condition: Function that takes a pixel value and returns a boolean.
    Returns:
        A PIL image with the mask.
    """
    img = img.convert("L")
    mask = np.zeros((img.size[1], img.size[0]), dtype = np.uint8)
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            if condition(img.getpixel((x, y))):
                mask[y, x] = 1
    mask = Image.fromarray(mask)
    return mask
        

def setup_data_generation(n):
    """Function that details data generation algorithm. It consists of 3 phases.
    Refer to the written report for a full explanation as to how it works.
    Total generation time is 20 minutes for 70 additional samples per class
    on a Ryzen 9 3900x CPU.
    
    Args:
        n: Number of data points to generate per class.
    """
    # Listing class names and data types
    class_names = ["fail_label_not_fully_printed", "fail_label_half_printed",
                   "fail_label_crooked_print", "no_fail"]
    data_types = ["train", "val", "test"]
    start_time = time.time()

    # Phase 1
    print("Getting class labels and saving filters without labels")
    get_removed_label(class_names, data_types)
    # Phase 2
    print("Matching filters")
    filter_coordinates = get_selected_filter()
    # Phase 3
    print("Generating Synthetic data")
    generate_synthetic_data(filter_coordinates, class_names, n)

    # Recording total time passed
    elapsed_time = time.time() - start_time
    print("Total data generation time (H/M/S) = ", 
          time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))


def check_prev_files(data_type: str, syn_data_path: str, classes: list):
    """Function that checks data directories if they exists. 
    Removes old files if they do exists.
    
    Args:
        data_type: Type of data (train, val, test).
        syn_data_path: Path to synthetic data directory.
        classes: List of class names.
    """
    if not os.path.exists(os.path.join(syn_data_path, data_type)):
        os.mkdir(os.path.join(syn_data_path, data_type))
        for data_class in classes:
            os.mkdir(os.path.join(syn_data_path, data_type, data_class))
    else:
        for data_class in classes:
            files_path = os.path.join(syn_data_path, data_type, data_class)
            files = os.listdir(files_path)
            for file in files:
                file_path = os.path.join(files_path, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)


def copy_list_files(samples: list, data_class: str, syn_data_path: str,
                    copy_type: str, data_type: str):
    """Function that copies a list of files from a directory to another.
    
    Args:
        samples: List of file names.
        data_class: Class name.
        syn_data_path: Path to synthetic data directory.
        copy_type: Type of data to copy (synthetic or real).
        data_type: Type of data (train, val, test).
    """
    if copy_type == "synthetic":
        path = SYNTHETIC_EX_PATH
    elif copy_type == "real":
        if data_type == "train":
            path = os.path.join("data", "NTZFilter", "train")
        elif data_type == "val":
            path = os.path.join("data", "NTZFilter", "val")
        elif data_type == "test":
            path = os.path.join("data", "NTZFilter", "test")

    for sample in samples:
        source_path = os.path.join(path, data_class, sample)
        destination_path = os.path.join(syn_data_path, data_type, data_class, sample)
        shutil.copyfile(source_path, destination_path)


def create_synthetic_dataset(train_set: int, val_set: int, test_set: int,
                             train_ratio: float, val_ratio: float, test_ratio: float,
                             no_combine: bool):
    """Function that creates a synthetic dataset, given the total sizes
    and the ratios between the real and synthetic data.
    
    Args:
        train_set: Number of training samples per class created synthetically.
        val_set: Number of validation samples per class created synthetically.
        test_set: Number of test samples per class created synthetically.
        train_ratio: Ratio of real samples to synthetic samples in the training set.
        val_ratio: Ratio of real samples to synthetic samples in the validation set.
        test_ratio: Ratio of real samples to synthetic samples in the test set.
        no_combine: Boolean that indicates whether to combine real and synthetic data.
    """

    if not os.path.exists(os.path.join("data", "NTZFilterSynthetic")):
        os.mkdir(os.path.join("data", "NTZFilterSynthetic"))
    syn_data_path = os.path.join("data", "NTZFilterSynthetic")
    classes = os.listdir(SYNTHETIC_EX_PATH)
    check_prev_files("train", syn_data_path, classes)
    check_prev_files("val", syn_data_path, classes)
    check_prev_files("test", syn_data_path, classes)

    for data_class in classes:
        # First copying from synthetic data
        samples = os.listdir(os.path.join(SYNTHETIC_EX_PATH, data_class))
        train_samples = samples[:train_set]
        val_samples = samples[train_set:train_set + val_set]
        test_samples = samples[train_set + val_set:train_set + val_set + test_set]
        copy_list_files(train_samples, data_class, syn_data_path, "synthetic", "train")
        copy_list_files(val_samples, data_class, syn_data_path, "synthetic", "val")
        copy_list_files(test_samples, data_class, syn_data_path, "synthetic", "test")

    if no_combine == False:
        # Copying from real dataset with combined method
        # If the set is 0, then the ratio is also 0 and then all data is real
        # so no subset has to be made
        for data_class in classes:
            if train_set == 0:
                train_samples = os.listdir(os.path.join("data", "NTZFilter", "train", data_class))
            else:
                total_samples = int(train_set / train_ratio)
                real_train_samples_n = total_samples - train_set 
                train_samples = os.listdir(os.path.join("data", "NTZFilter", "train", data_class))[:real_train_samples_n]
            if val_set == 0:
                val_samples = os.listdir(os.path.join("data", "NTZFilter", "val", data_class))
            else:
                total_samples = int(val_set / val_ratio)
                real_val_samples_n = total_samples - val_set 
                val_samples = os.listdir(os.path.join("data", "NTZFilter", "val", data_class))[:real_val_samples_n]
            # same thing but for the test set
            if test_set == 0:
                test_samples = os.listdir(os.path.join("data", "NTZFilter", "test", data_class))
            else:
                total_samples = int(test_set / test_ratio)
                real_test_samples_n = total_samples - test_set 
                test_samples = os.listdir(os.path.join("data", "NTZFilter", "test", data_class))[:real_test_samples_n]
            copy_list_files(train_samples, data_class, syn_data_path, "real", "train")
            copy_list_files(val_samples, data_class, syn_data_path, "real", "val")
            copy_list_files(test_samples, data_class, syn_data_path, "real", "test")
    else:
        # Copying from real dataset without combining
        for data_class in classes:
            train_samples = os.listdir(os.path.join("data", "NTZFilter", "train", data_class))
            val_samples = os.listdir(os.path.join("data", "NTZFilter", "val", data_class))
            test_samples = os.listdir(os.path.join("data", "NTZFilter", "test", data_class))
            copy_list_files(train_samples, data_class, syn_data_path, "real", "train")
            copy_list_files(val_samples, data_class, syn_data_path, "real", "val")
            copy_list_files(test_samples, data_class, syn_data_path, "real", "test")


if __name__ == '__main__':
    # train_set is the number of training samples per class created synthetically
    # val_set is the number of validation samples per class created synthetically
    # train_ratio is ratio of real samples to synthetic samples in the training set
    # val_ratio is ratio of real samples to synthetic samples in the validation set
    # if a ratio is 1, then the dataset is only synthetic
    # if a ratio is 0.5, then the dataset is half real and half synthetic
    # if a ratio is 0, then the dataset is only real, but this option is disabled
    # Example input: python3.10 synthetic_data.py 150 0 20 0 20 0 --no_combine
    parser = argparse.ArgumentParser()
    parser.add_argument("train_set", type = int)
    parser.add_argument("train_ratio", type = float)
    parser.add_argument("val_set", type = int)
    parser.add_argument("val_ratio", type = float)
    parser.add_argument("test_set", type = int)
    parser.add_argument("test_ratio", type = float)
    parser.add_argument("--no_combine", action = "store_true")
    args = parser.parse_args()
    n = args.train_set + args.val_set + args.test_set

    # Create synthetic data directories
    classes = ["fail_label_not_fully_printed", "fail_label_half_printed",
                   "fail_label_crooked_print", "no_fail"]
    print("Creating Synthetic data directories")
    create_synthetic_data_dirs(classes)

    # Check if ratios are valid
    if args.train_ratio < 0 or args.train_ratio > 1 \
       or args.val_ratio < 0 or args.val_ratio > 1 \
       or args.test_ratio < 0 or args.test_ratio > 1:
        print("Invalid ratio, exiting...")
        exit()

    # Checking if set and ratio confirm
    if args.no_combine == False:
        if ((args.train_set == 0) ^ (args.train_ratio == 0)) or \
           ((args.val_set == 0) ^ (args.val_ratio == 0)) or \
           ((args.test_set == 0) ^ (args.test_ratio == 0)):
            print("Invalid set size, ratio combination, exiting...")
            exit()

    # If combining is disabled, the datasets just need to be combined without checking
    # This is the case with all experiment that use synthetic data without 
    # explicitly testing it
    if args.no_combine == False:
        if args.train_ratio < 1 and args.train_ratio != 0:
            # Real data is used, hence check if the set size is ok
            # Min amount of samples for the train set for all classes is 48
            if (args.train_set / args.train_ratio) * (1 - args.train_ratio) > 48:
                print("Train set size is too large, exiting...")
                exit()

        if args.val_ratio < 1 and args.val_ratio != 0:
            # Real data is used, hence check if the set size is ok
            # Min amount of samples for the val set for all classes is 6
            if (args.val_set / args.val_ratio) * (1 - args.val_ratio) > 6:
                print("Validation set size is too large, exiting...")
                exit()

        if args.test_ratio < 1 and args.test_ratio != 0:
            # Real data is used, hence check if the set size is ok
            # Min amount of samples for the test set for all classes is 6
            if (args.test_set / args.test_ratio) * (1 - args.test_ratio) > 6:
                print("Test set size is too large, exiting...")
                exit()

    # Check if enough synthetic data already exists and hence does not
    # need to be regenerated
    for data_class in classes:
        class_samples = os.listdir(os.path.join(SYNTHETIC_EX_PATH, data_class))
        if len(class_samples) < n:
            setup_data_generation(n)
            break
    
    create_synthetic_dataset(args.train_set, args.val_set, args.test_set,
                             args.train_ratio, args.val_ratio, args.test_ratio,
                             args.no_combine)