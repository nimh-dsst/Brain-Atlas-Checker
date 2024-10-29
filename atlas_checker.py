from pathlib import Path
import json
from typing import Set
import csv

import click
import tifffile


def get_unique_values_from_tiff_dir(directory_path: str | Path) -> set:
    """
    Parses a directory containing TIFF files and returns a set of all unique values in those images.

    Args:
        directory_path (str | Path): Path to the directory containing the TIFF files.

    Returns:
        set: A set of unique values found in the TIFF files.
    """
    unique_values: set = set()

    # Iterate through all files in the directory
    for file_path in Path(directory_path).glob("*.tif"):
        try:
            # Read the TIFF file
            with tifffile.TiffFile(file_path) as tif:
                image_data = tif.asarray()

            # Add unique values to the set
            unique_values.update(image_data.flatten())
        except Exception as e:
            print(f"Error processing file {file_path}: {str(e)}")

    return unique_values


def get_csv_ids(
    csv_path: str | Path = "./atlases/atlas_v3/atlas_info.csv",
) -> set[int]:
    """
    Parses the atlas info CSV file and extracts all unique IDs.

    Args:
        csv_path (str | Path): Path to the CSV file. Defaults to standard location.

    Returns:
        set[int]: Set of unique integer IDs from the CSV file.

    Raises:
        FileNotFoundError: If the CSV file doesn't exist
        ValueError: If there are invalid entries in the ID column
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found at {csv_path}")

    unique_ids = set()
    try:
        with open(csv_path, "r", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                try:
                    unique_ids.add(int(row["id"]))
                except ValueError as e:
                    raise ValueError(
                        f"Invalid ID value in CSV: {row['id']}"
                    ) from e
    except csv.Error as e:
        raise ValueError(f"Error parsing CSV file: {str(e)}")

    return unique_ids


def scan_for_label_directories(
    root_path: str | Path, csv_path: str | Path
) -> dict[str, set[int]]:
    """
    Recursively scans for directories named 'atlaslabel_def_origspace',
    gets unique values from TIFF files, and identifies values not present in the CSV.

    Args:
        root_path (str | Path): The root directory to start the recursive search from.
        csv_path (str | Path): Path to the CSV file containing valid IDs.

    Returns:
        Dict[str, set[int]]: A dictionary where keys are absolute paths to found
            directories and values are sets of IDs present in TIFF files but not in CSV.
    """
    results = {}

    # Convert to Path object if string was provided
    if isinstance(root_path, str):
        root_path = Path(root_path)

    # Ensure the root path exists
    if not root_path.exists():
        raise ValueError(f"Root path {root_path} does not exist")

    # Get CSV IDs once at the start
    csv_ids = get_csv_ids(csv_path)

    # Recursively search for directories with the target name
    target_dirs = root_path.rglob("atlaslabel_def_origspace")

    # Process each found directory
    for directory in target_dirs:
        if directory.is_dir():  # Ensure it's a directory
            try:
                # Get absolute path as string for dictionary key
                abs_path = str(directory.absolute())

                # Get unique values from TIFF files
                tiff_values = get_unique_values_from_tiff_dir(directory)

                # Convert TIFF values to integers and filter out non-integer values
                tiff_integers = set()
                for value in tiff_values:
                    try:
                        tiff_integers.add(int(value))
                    except (ValueError, TypeError):
                        continue

                # Find missing IDs through set subtraction
                results[abs_path] = tiff_integers - csv_ids

                print(f"Successfully processed directory: {abs_path}")
            except Exception as e:
                print(f"Error processing directory {directory}: {str(e)}")

    return results


class SetEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle sets."""

    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


@click.command()
@click.argument(
    "root_directory",
    type=click.Path(
        exists=True, file_okay=False, dir_okay=True, path_type=Path
    ),
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False),
    help="Output JSON file path (optional)",
)
@click.option(
    "--verbose", "-v", is_flag=True, help="Print detailed progress information"
)
@click.option(
    "--csv-path",
    type=click.Path(exists=True, dir_okay=False),
    default="./atlases/atlas_v3/atlas_info.csv",
    help="Path to atlas info CSV file",
)
def main(
    root_directory: Path, output: str | None, verbose: bool, csv_path: str
) -> None:
    """
    Scan for TIFF files in 'atlaslabel_def_origspace' directories and find values not present in CSV.

    ROOT_DIRECTORY: The starting directory for the recursive search.
    """
    if verbose:
        click.echo(f"Starting scan from root directory: {root_directory}")
        click.echo(f"Using CSV file: {csv_path}")

    try:
        # Get results directly as missing IDs
        results = scan_for_label_directories(root_directory, csv_path)

        if verbose:
            click.echo(f"\nFound {len(results)} matching directories")

        if output:
            # Save results to JSON
            with open(output, "w") as f:
                json.dump(results, f, cls=SetEncoder, indent=2)
            click.echo(f"\nResults saved to: {output}")
        else:
            # Print results to console
            for directory, missing_ids in results.items():
                click.echo(f"\nDirectory: {directory}")
                click.echo(
                    f"IDs present in TIFF but missing from CSV: {sorted(missing_ids)}"
                )

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    main()
