import logging
import sys


def configure_logging(
    level: int = logging.INFO,
) -> None:
    """
    Configure application-wide logging.
    """

    logging.basicConfig(
        level=level,
        format=(
            "%(asctime)s | "
            "%(levelname)-8s | "
            "%(name)s | "
            "%(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )
