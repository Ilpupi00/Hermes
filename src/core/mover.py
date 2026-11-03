from pathlib import Path
from .config import logger

def move_file(source: Path , dest_dir: Path)-> Path:
    """Sposta atomicamente un file; sorgente e destinazione devono condividere il filesystem."""
    dest_path=dest_dir/source.name

    try:
        source.replace(dest_path)
        logger.info(f"file={source.name} status=moved_to_{dest_dir.name}")
        return dest_path
    except Exception as e:
        logger.error(f"file={source.name} status=move_error error={str(e)}")
        raise e
