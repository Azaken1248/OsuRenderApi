from src.core.config import get_settings

def serialize_error(error_message: str | None, debug: bool = None) -> str | None:
    if not error_message:
        return error_message
        
    if debug is None:
        debug = get_settings().debug
        
    if debug:
        return error_message

    return "An internal rendering error occurred."
