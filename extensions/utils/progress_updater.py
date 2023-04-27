class ProgressUpdater:
    def __init__(self) -> None:
        pass

    def print_progress_bar(
        self,
        iteration,
        total,
        prefix="",
        suffix="Complete",
        length=50,
        fill="█",
        print_end="\r",
        is_done=False,
    ):
        """
        Call in a loop to create a terminal progress bar.
        iteration - Required : current iteration (Int)
        total - Required : total iterations (Int)
        prefix - Optional : prefix string (Str)
        suffix - Optional : suffix string (Str)
        length - Optional : character length of the progress bar (Int)
        fill - Optional : bar fill character (Str)
        print_end - Optional : end character (e.g. "\r", "\r\n") (Str)
        """
        percent = ("{0:.1f}").format(100 * (iteration / float(total)))
        filled_length = int(length * iteration // total)
        bar = fill * filled_length + "-" * (length - filled_length)

        if not is_done:
            print(
                f"\r{prefix} |{bar}| {percent}% {suffix} | {iteration}/{total}",
                end=print_end,
            )
        else:
            print(
                f"\rCompleted: {iteration}/{total} YAY!!",
                end=print_end,
            )

        # Print a new line when complete
        if iteration == total:
            print()
