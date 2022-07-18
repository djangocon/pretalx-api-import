# import requests
import frontmatter
import json
import typer

from pathlib import Path
from rich import print
from slugify import slugify


app = typer.Typer()


@app.command()
def main(input_filename: Path, output_folder: Path = None):
    typer.echo("process")
    rows = json.loads(input_filename.read_text())

    # {
    #     "Abstract": "",
    #     "Average (mean) score": 0.0,
    #     "created": "2022-05-31T10:24:20.588579+00:00",
    #     "Description": "",
    #     "Don't record this session.": False,
    #     "Duration": 45,
    #     "End": None,
    #     "ID": "3NA7TZ",
    #     "Internal notes": None,
    #     "Language": "en",
    #     "Median score": "2.00",
    #     "Notes": "",
    #     "Pending proposal state": None,
    #     "Proposal state": "submitted",
    #     "Proposal title": "",
    #     "Resources": None,
    #     "Room": None,
    #     "Session image": "",
    #     "Session type": {"en": "45-minute talks"},
    #     "Show this session in public list of featured sessions.": False,
    #     "Slot Count": 1,
    #     "Speaker IDs": ["ID1234"],
    #     "Speaker names": ["Firstname Lastname"],
    #     "Start": None,
    #     "Tags": None,
    #     "Track": {"en": "General"},
    # }

    print(rows[0:4])
    print(f"Processing {len(rows)} rows...")
    for row in rows:
        proposal_state = row["Proposal state"]
        if proposal_state in ["accepted", "confirmed"]:
            talk_format = row["Session type"]["en"]
            talk_title_slug = slugify(row["Proposal title"])

            post = frontmatter.loads(row["Description"])
            post["abstract"] = row["Abstract"]
            post["accepted"] = True if proposal_state == "accepted" else False
            post["category"] = talk_format
            # post["difficulty"] = submission["talk"]["audience_level"]
            post["layout"] = "session-details"
            post["permalink"] = f"/{talk_format}/{talk_title_slug}/"
            post["published"] = True
            post["sitemap"] = True
            post["slug"] = talk_title_slug
            post["tags"] = row["Tags"]
            post["title"] = row["Proposal title"]

            # print(row["Session type"]["en"])
            # print(row["Speaker names"])
            # print(row["Track"]["en"])

            # # TODO: Scheduling info...
            # post["date"] = f"{start_date} 10:00"
            # post["room"] = ""
            # post["track"] = "t0"

            # TODO: Determine if we still need summary (I don't think we do)
            post["summary"] = ""

            # todo: refactor template layout to support multiple authors
            post["presenters"] = row["Speaker names"]

            # print(frontmatter.dumps(post))


if __name__ == "__main__":
    app()
