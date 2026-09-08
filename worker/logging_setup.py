import logging


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "\n%(asctime)s | %(levelname)s | %(name)s\n"
            "📄 %(filename)s:%(lineno)d\n"
            "%(message)s\n"
        ),
    )