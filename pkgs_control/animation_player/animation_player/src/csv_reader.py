import csv
import os


class CSVReader:
    def __init__(self, csv_file_path, loop=True):
        self.csv_file_path = csv_file_path
        # Hvis loop=True wrapper get_next_row tilbage til foerste data-row
        # naar slutningen naas (legacy default — brugt af eksterne kaldere
        # der forventer uendelig stroem). Hvis loop=False returnerer den
        # None ved EOF, saa kalderen kan stoppe pent.
        self.loop = loop

        # Check if the file exists and is readable
        if not os.path.exists(self.csv_file_path):
            raise FileNotFoundError(f"File not found: {self.csv_file_path}")

        # Initialize file and reader
        self.open_file()

    def open_file(self):
        """Opens the file and initializes the CSV reader and header."""
        self.file = open(self.csv_file_path, mode="r")
        self.csv_reader = csv.reader(self.file)

        try:
            # Read and store the header (first row)
            self.header = next(self.csv_reader)
        except StopIteration:
            raise ValueError(f"CSV file '{self.csv_file_path}' is empty.")

    def reset_iterator(self):
        """Closes the current file and reopens it to reset the iterator."""
        self.file.close()
        self.open_file()

    def get_next_row(self):
        """Iteraties to next row of CSV.

        Hvis loop=True (default): wrapper tilbage til foerste data-row ved
        EOF og returnerer den.
        Hvis loop=False: returnerer None ved EOF, saa kalderen kan signalere
        end-of-animation."""
        try:
            return next(self.csv_reader)
        except StopIteration:
            if not self.loop:
                return None
            self.reset_iterator()
            try:
                return next(self.csv_reader)
            except StopIteration:
                # Filen havde kun en header — helt tom efter reset.
                # Burde aldrig ske (open_file kraever at header eksisterer)
                # men returner None fremfor at recurse uendeligt.
                return None

    def close(self):
        """Closes the file when done."""
        self.file.close()

    def get_header(self):
        return self.header
