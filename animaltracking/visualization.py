import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Optional
from loguru import logger
import skimage

def create_heatmap_report(points:np.ndarray, image:Optional[np.ndarray]=None, filename:Optional[Path]=None):
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
    plt.subplots_adjust(top=1, bottom=0, right=1, left=0,
                        hspace=0, wspace=0)
    plt.margins(0, 0)
    plt.gca().xaxis.set_major_locator(plt.NullLocator())
    plt.gca().yaxis.set_major_locator(plt.NullLocator())

    x, y = points[:, 0], points[:, 1]
    sns.kdeplot(
        x=x, y=y,
        fill=True,
        # thresh=0.1,
        # levels=100,
        # cmap="mako",
        # cmap="jet",
        # palette="jet",
        # cmap="crest",
        cmap="rocket",
        alpha=.5,
        linewidth=0
    )
    if filename is not None:
        # plt.savefig(Path(filename))
        plt.savefig(Path(filename), bbox_inches='tight', pad_inches=0)
        plt.close(fig)

    return fig