def retry_delay(attempt):
    """Seconds before retrying a failed request, with a bounded exponential delay."""
    return min(2 ** attempt, 30)
