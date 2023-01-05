import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Optional
from loguru import logger
import skimage
import cv2


def create_heatmap_report(
    points: np.ndarray,
    image: Optional[np.ndarray] = None,
    filename: Optional[Path] = None,
    show_trajectory:bool=True,
):
    """
    :param points: xy points with shape = [i,2]
    :param image: np.ndarray with image
    :param filename: if filename is set the savefig is called and fig is closed
    :return: figure
    """
    # logger.debug(points)
    points = np.asarray(points)
    # logger.debug(f"points.shape={points.shape}")

    if points.ndim != 2:
        logger.warning("No points found for heatmap")
        return None

    fig = plt.figure()
    if isinstance(image, np.ndarray):
        im_gray = skimage.color.rgb2gray(image[:, :, ::-1])
        plt.imshow(im_gray, cmap="gray")
    plt.axis("off")

    plt.gca().set_axis_off()
    plt.subplots_adjust(top=1, bottom=0, right=1, left=0, hspace=0, wspace=0)
    plt.margins(0, 0)
    plt.gca().xaxis.set_major_locator(plt.NullLocator())
    plt.gca().yaxis.set_major_locator(plt.NullLocator())

    x, y = points[:, 0], points[:, 1]
    sns.kdeplot(
        x=x,
        y=y,
        fill=True,
        # thresh=0.1,
        # levels=100,
        # cmap="mako",
        # cmap="jet",
        # palette="jet",
        # cmap="crest",
        cmap="rocket",
        alpha=0.5,
        linewidth=0,
    )
    if show_trajectory:
        plt.plot(points[:,0], points[:,1], "b")
    if filename is not None:
        # plt.savefig(Path(filename))
        plt.savefig(Path(filename), bbox_inches="tight", pad_inches=0)
        plt.close(fig)

    return fig



def insert_ruler_in_image(img, pixelsize, ruler_size=50, resize_factor=1., unit='mm'):
    image_size = np.asarray(img.shape[:2])
    # start_point = np.asarray(image_size) * 0.90
    # start_point = np.array([10,10])
    thickness = int(0.01 * img.shape[0]/resize_factor)
    # start_point = np.array([image_size[1]*0.98, image_size[0]*0.97]) # right down corner
    start_point = np.array([image_size[1]*0.02, image_size[0]*0.97])
    ruler_size_px = ruler_size / pixelsize
    end_point = start_point + np.array([ruler_size_px,0])

    cv2.line(img, start_point.astype(int), end_point.astype(int), (255,255,255), thickness)

    text_point = start_point.astype(np.int) - np.array([0,int(0.020 * img.shape[0])/resize_factor]).astype(int)
    # img[line]
    text_thickness = int(0.004 * img.shape[0]/resize_factor)
    # logger.debug(f"ruler_size_px={ruler_size_px}")
    # logger.debug(f"text_point={text_point}")
    # logger.debug(f"text_thickness={text_thickness}")
    cv2.putText(
        img,
        f"{ruler_size:0.0f} [{unit}]",
        text_point,
        # (int(position[0]+(circle_radius*2.5)), int(position[1]+circle_radius*0)),
        cv2.FONT_HERSHEY_SIMPLEX,
        fontScale=.0007 * img.shape[0]/resize_factor,
        color=(255,255,255),
        thickness=text_thickness
    )
    return img
