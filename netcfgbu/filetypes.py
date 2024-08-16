import csv


class CommentedCsvReader(csv.DictReader):
    """
    A CSV reader that skips rows starting with a comment character ('#').

    This class extends `csv.DictReader` to ignore lines where the first column
    starts with the comment character '#'. It processes the CSV file and returns
    the next valid row as a dictionary.

    Example usage:
        reader = CommentedCsvReader(file)
        for row in reader:
            # Process each row

    Methods:
        __next__: Returns the next valid row from the CSV file, skipping commented rows.
    """

    def __next__(self):
        """
        Return the next row from the CSV file, skipping rows where the first column
        starts with the comment character '#'.

        Returns:
            dict: The next valid row as a dictionary.

        Raises:
            StopIteration: When there are no more rows to return.
        """
        value = super().__next__()

        if value[self.fieldnames[0]].startswith("#"):
            return self.__next__()

        return value


# TODO: not in use just yet.
# class TextFileReader:
#     wordsep_re = re.compile(r"\s+|,")
#
#     def __init__(self, fileio, index=0):
#         self._index = index
#         self._lines = fileio.readlines()
#
#     def __iter__(self):
#         return self
#
#     def __next__(self):
#         try:
#             line_item = self._lines.pop(0)
#         except IndexError:
#             raise StopIteration
#
#         if line_item.startswith("#"):
#             return self.__next__()
#
#         try:
#             return self.wordsep_re.split(line_item)[self._index]
#         except IndexError:
#             pass
#
#         return self.__next__()
