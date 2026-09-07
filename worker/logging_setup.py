import logging


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s %(levelname)s %(name)s "
            "%(filename)s:%(lineno)d %(message)s"
        ),
    )
