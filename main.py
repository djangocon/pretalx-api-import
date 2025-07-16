# import requests
import datetime as pydatetime  # rename is needed because of yaml conflict
import json

import frontmatter
import pytz
import typer
import requests

from itertools import count
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from pathlib import Path
from pydantic import BaseModel, ValidationError
from rich import print
from slugify import slugify

from typing import Literal, Optional

from pydantic import BaseModel


CONFERENCE_TZ = pytz.timezone("America/Chicago")
# we listed tutorials as being 180 minutes in pretalx but we
# want to have them take up 210 minutes in the layout
TUTORIAL_LENGTH_OVERRIDE = relativedelta(hours=3, minutes=30)


class FrontmatterModel(BaseModel):
    """
    Our base class for our default "Frontmatter" fields.
    """

    permalink: str | None = None
    redirect_from: list[str] | None = None
    redirect_to: str | None = None  # via the jekyll-redirect-from plugin
    sitemap: bool | None = None
    title: str | None = None


class Social(BaseModel):
    github: str | None = None
    website: str | None = None
    mastodon: str | None = None
    twitter: str | None = None
    bluesky: str | None = None
    instagram: str | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.mastodon and self.mastodon.startswith("@"):
            self.mastodon = migrate_mastodon_handle(handle=self.mastodon)
            print(f"🚜 converting {self.mastodon=}")


class Organizer(FrontmatterModel):
    hidden: bool = False
    name: str
    photo: str | None = None
    slug: str | None = None
    title: str | None = None
    social: Social | None = None


class Page(FrontmatterModel):
    description: str | None = None
    heading: str | None = None
    hero_text_align: str | None = None  # homepage related
    hero_theme: str | None = None  # homepage related
    testimonial_img: str | None = None  # homepage related
    testimonial_img_mobile: str | None = None  # homepage related
    title: str | None = None


class Post(FrontmatterModel):
    author: str | None = None
    category: str | None = "General"  # TODO: build a list of these
    categories: list[str] | None = None
    date: pydatetime.datetime  # YYYY-MM-DD HH:MM:SS +/-TTTT
    image: str | None = None
    slug: str | None = None
    tags: list[str] | None = []


class Presenter(FrontmatterModel):
    company: str | None = None
    hidden: bool = False
    name: str
    override_schedule_title: str | None = None
    pronouns: str | None = None
    photo: str | None = None
    role: str | None = None
    social: Social | None = None

    def __init__(self, **data):
        super().__init__(**data)

        # if permalink is blank, let's build a new one
        if not self.permalink:
            self.permalink = f"/presenters/{slugify(self.name)}/"


class Schedule(FrontmatterModel):
    category: Literal[
        "break",
        "lunch",
        "rooms",
        "social-event",
        "sprints",
        "talks",
        "tutorials",
    ]
    difficulty: str | None = "All"
    end_datetime: pydatetime.datetime | None = None
    sitemap: bool = True
    image: str | None = None
    presenter_slugs: list[str] | None = None
    room: str | None = None
    show_video_urls: bool | None = None
    slides_url: str | None = None
    datetime: pydatetime.datetime | None
    tags: list[str] | None = None
    track: str | None = None
    video_url: str | None = None

    def __init__(self, **data):
        super().__init__(**data)


class ManualScheduleEntry(BaseModel):
    datetime: pydatetime.datetime
    end_datetime: pydatetime.datetime
    permalink: str | None
    room: str
    title: str


POST_TYPES = [
    {"path": "_organizers", "class_name": Organizer},
    {"path": "_pages", "class_name": Page},
    {"path": "_posts", "class_name": Post},
    {"path": "presenters", "class_name": Presenter},
    {"path": "schedule", "class_name": Schedule},
]

TRACKS = {
    "Room A": "t0",
    "Room B": "t1",
    # TODO figure out if we need to tweak the template for online talks or
    # how we want to adjust this
    "Online talks": "t2",
    # tutorials
    "Tutorial Track A": "t0",
    "Tutorial Track B": "t1",
    "Tutorial Track C": "t2",
}

TALK_FORMATS = {
    "25-minute talks": "talks",
    "45-minute talks": "talks",
    "Tutorials": "tutorials",
}


app = typer.Typer()


@app.command()
def presenters(
    input_filename: Path,
    # typer doesn't support Path | None
    output_folder: Optional[Path] = None,
):
    rows = json.loads(input_filename.read_text())
    # [
    #     "ID",
    #     "Name",
    #     "E-Mail",
    #     "Biography",
    #     "Picture",
    #     "Proposal IDs",
    #     "Proposal titles",
    #     "Organization or Affiliation",
    #     "URL",
    #     "What is your T-shirt size?",
    #     "What is your mastodon/fediverse handle?"
    #     "Twitter handle",
    # ]
    print(rows[0])
    print(f"Processing {len(rows)} rows...")
    anon_speaker_counter = count()
    for row in rows:
        default_profile_pic = None
        presenter_path: Path | None = None
        try:
            if output_folder is not None:
                # is there already a pic in the directory?
                presenter_path = output_folder / "src" / "_content" / "presenters"
                if shots := list(presenter_path.glob(f"{slugify(row.get('Name'))}.*")):
                    for shot in shots:
                        if not shot.name.endswith(".md"):
                            default_profile_pic = shot.name
                            break

            bio = row.get("Biography") or ""
            post = frontmatter.loads(
                "\n".join(line.rstrip() for line in bio.splitlines()) or ""
            )
            name = row.get("Name")
            if not name:
                name = f"Anonymous speaker {next(anon_speaker_counter)}"
            data = Presenter(
                company=row.get("Organization or Affiliation", ""),
                hidden=False,
                name=name,
                # override_schedule_title: str | None = None
                permalink=f"/presenters/{slugify(name)}/",
                photo=default_profile_pic or row.get("Picture", None),
                social=Social(
                    github=row.get("github"),
                    mastodon=row.get("What is your mastodon/fediverse handle?"),
                    website=row.get("URL"),
                    twitter=row.get("Twitter handle"),
                    instagram=row.get("instagram"),
                    bluesky=row.get("bluesky"),
                ),
            )
            if presenter_path and data.photo and data.photo.startswith("http"):
                # fetch the externally hosted image and save it ourselves
                try:
                    response = requests.get(data.photo)
                    response.raise_for_status()
                except (requests.ConnectionError, requests.RequestException) as exc:
                    typer.secho(
                        f"Error downloading profile picture for {data.name}: {exc}",
                        fg="red",
                    )
                else:
                    if "." in data.photo.rsplit("/", 1):
                        filename = (
                            f'{slugify(data.name)}.{data.photo.rsplit(".", 1)[-1]}'
                        )
                    else:
                        content_type = response.headers["Content-Type"]
                        if (
                            content_type.startswith("image/")
                            and "+" not in content_type
                        ):
                            filename = f'{slugify(data.name)}.{content_type.rsplit("/", 1)[-1]}'
                        else:
                            raise ValueError(
                                f"Don't know how to handle content type {content_type}"
                            )

                    image_output_path: Path = presenter_path / filename
                    image_output_path.write_bytes(response.content)
                    data.photo = image_output_path.name

            if data.social.twitter and data.social.twitter.startswith("@"):
                # strip leading @ if present
                data.social.twitter = data.social.twitter[1:]

            if data.social.mastodon:
                data.social.mastodon = migrate_mastodon_handle(
                    handle=data.social.mastodon
                )

            post.metadata.update(data.model_dump(exclude_unset=True))

            if output_folder is not None:
                output_path: Path = (
                    output_folder
                    / "src"
                    / "_content"
                    / POST_TYPES[-2]["path"]
                    / f"{slugify(data.name)}.md"
                )
                output_path.write_text(frontmatter.dumps(post, indent=4) + "\n")

        except ValidationError as e:
            print(f"[red]{row}[/red]")
            print(e.json())

        except Exception as e:
            print(f"[red]{e}[/red]")
            print(row)


@app.command()
def main(input_filename: Path, output_folder: Path = None):
    rows = json.loads(input_filename.read_text())
    # [
    #     "ID",
    #     "Proposal title",
    #     "Proposal state",
    #     "Pending proposal state",
    #     "Session type",
    #     "Track",
    #     "created",
    #     "Tags",
    #     "Abstract",
    #     "Description",
    #     "Notes",
    #     "Internal notes",
    #     "Duration",
    #     "Slot Count",
    #     "Language",
    #     "Show this session in public list of featured sessions.",
    #     "Don't record this session.",
    #     "Session image",
    #     "Speaker IDs",
    #     "Speaker names",
    #     "Room",
    #     "Start",
    #     "End",
    #     "Median score",
    #     "Average (mean) score",
    #     "Resources",
    # ]
    print(rows[0].keys())
    print(rows[0])
    print(f"Processing {len(rows)} rows...")
    for row in rows:
        proposal_state = row["Proposal state"]
        if proposal_state in ["accepted", "confirmed"]:
            talk_format = row["Session type"]["en"]
            talk_title_slug = slugify(row["Proposal title"])

            post = frontmatter.loads(row["Description"])
            start_date = None
            end_date = None
            if raw_start_date := row.get("Start"):
                start_date = parse(raw_start_date).astimezone(CONFERENCE_TZ)
            if raw_end_date := row.get("End"):
                end_date = parse(raw_end_date).astimezone(CONFERENCE_TZ)
            if start_date and TALK_FORMATS.get(talk_format) == "tutorials":
                end_date = start_date + TUTORIAL_LENGTH_OVERRIDE
            room = row["Room"]["en"]
            try:
                data = Schedule(
                    category=TALK_FORMATS[talk_format],
                    # post["difficulty"] = submission["talk"]["audience_level"],
                    permalink=f"/{TALK_FORMATS[talk_format]}/{talk_title_slug}/",
                    tags=row["Tags"],
                    title=row["Proposal title"]
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"),
                    presenter_slugs=[slugify(name) for name in row["Speaker names"]],
                    room=room,
                    track=TRACKS.get(room, "t0"),
                    datetime=start_date,
                    end_datetime=end_date,
                )

                post.metadata.update(data.model_dump(exclude_unset=True))

                if output_folder is not None:
                    output_path: Path = (
                        output_folder
                        / "src"
                        / "_content"
                        / POST_TYPES[-1]["path"]
                        / data.category
                        # TODO please make this less ugly
                        / f"{data.datetime.year}-{data.datetime.month:0>2}-{data.datetime.day:0>2}-"
                        f"{data.datetime.hour:0>2}-{data.datetime.minute:0>2}-{data.track}-{slugify(data.title)}.md"
                    )
                    output_path.write_text(frontmatter.dumps(post))
                else:
                    print(frontmatter.dumps(post))

            except ValidationError as e:
                print(f"[red]{row}[/red]")
                print(e.json())
                raise

            except Exception as e:
                print(f"[red]{e}[/red]")
                print(row)
                raise


def migrate_mastodon_handle(*, handle: str) -> str | None:
    if not handle.startswith("@"):
        return handle
    try:
        username, domain = handle[1:].split("@")
    except ValueError:
        print(f"[red]Invalid mastodon value: {handle}[/red]")
        return None
    return f"https://{domain}/@{username}"


if __name__ == "__main__":
    app()
