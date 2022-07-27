# import requests
import frontmatter
import json
import pytz
import typer

from datetime import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
from pathlib import Path
from pydantic import BaseModel, Field, ValidationError
from rich import print
from slugify import slugify
from typing import List, Optional


CONFERENCE_TZ = pytz.timezone("America/Los_Angeles")
# we listed tutorials as being 180 minutes in pretalx but we
# want to have them take up 210 minutes in the layout
TUTORIAL_LENGTH_OVERRIDE = relativedelta(hours=3, minutes=30)


class FrontmatterModel(BaseModel):
    """
    Our base class for our default "Frontmatter" fields.
    """

    date: Optional[datetime]
    layout: str
    permalink: Optional[str]
    published: bool = True
    redirect_from: Optional[List[str]]
    redirect_to: Optional[str]  # via the jekyll-redirect-from plugin
    sitemap: Optional[bool]
    title: str

    class Config:
        extra = "allow"


class Job(FrontmatterModel):
    hidden: bool = False
    layout: str = "base"
    name: str
    title: Optional[str]
    website: str
    website_text: str = "Apply here"


class Organizer(FrontmatterModel):
    github: Optional[str]
    hidden: bool = False
    layout: str = "base"
    name: str
    photo_url: Optional[str]
    slug: Optional[str]
    title: Optional[str]
    twitter: Optional[str]
    website: Optional[str]


class Page(FrontmatterModel):
    description: Optional[str]
    heading: Optional[str]
    hero_text_align: Optional[str]  # homepage related
    hero_theme: Optional[str]  # homepage related
    layout: Optional[str]
    testimonial_img: Optional[str]  # homepage related
    testimonial_img_mobile: Optional[str]  # homepage related
    title: Optional[str]


class Post(FrontmatterModel):
    author: Optional[str] = None
    category: Optional[str] = "General"  # TODO: build a list of these
    categories: Optional[List[str]]
    date: datetime  # YYYY-MM-DD HH:MM:SS +/-TTTT
    image: Optional[str] = None
    layout: Optional[str] = "post"
    slug: Optional[str] = None
    tags: Optional[List[str]]


class Presenter(FrontmatterModel):
    company: Optional[str]
    github: Optional[str]
    hidden: bool = False
    layout: str = "speaker-template"
    name: str
    override_schedule_title: Optional[str] = None
    photo_url: Optional[str]
    role: Optional[str]
    title: Optional[str]
    twitter: Optional[str]
    website: Optional[str]
    website_text: str = "Apply here"


class Schedule(FrontmatterModel):
    abstract: Optional[str] = None
    accepted: bool = False
    category: Optional[str] = "talk"
    difficulty: Optional[str] = "All"
    image: Optional[str]
    layout: Optional[str] = "session-details"  # TODO: validate against _layouts/*.html
    presenter_slugs: Optional[List[str]] = None
    presenters: List[dict] = None  # TODO: break this into a sub-type
    published: bool = False
    room: Optional[str]
    schedule: Optional[str]
    schedule_layout: Optional[str] = Field(
        alias="schedule-layout"
    )  # TODO: Validate for breaks, lunch, etc
    show_video_urls: Optional[bool]
    slides_url: Optional[str]
    summary: Optional[str]
    end_date: Optional[datetime] = None
    tags: Optional[List[str]] = None
    talk_slot: Optional[str] = "full"
    track: Optional[str] = None
    video_url: Optional[str]


POST_TYPES = [
    {"path": "_jobs", "class_name": Job},
    {"path": "_organizers", "class_name": Organizer},
    {"path": "_pages", "class_name": Page},
    {"path": "_posts", "class_name": Post},
    {"path": "_presenters", "class_name": Presenter},
    {"path": "_schedule", "class_name": Schedule},
]

TRACKS = {
    "Salon A-E": "t0",
    "Salon F-H": "t1",
    # TODO figure out if we need to tweak the template for online talks or
    # how we want to adjust this
    "Online talks": "t2",
    # tutorials
    "Balboa I & II": "t0",
    "Sierra 5": "t1",
    "Cabrillo 1": "t2",
}

TALK_FORMATS = {
    "25-minute talks": "talks",
    "45-minute talks": "talks",
    "Tutorials": "tutorials",
}


app = typer.Typer()


@app.command()
def presenters(input_filename: Path, output_folder: Optional[Path] = None):
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
    #     "Twitter handle",
    # ]
    print(rows[0])
    print(f"Processing {len(rows)} rows...")
    for row in rows:
        try:
            if output_folder is not None:
                # is there already a pic in the directory?
                presenter_path: Path = output_folder / "static" / "img" / "presenters"
                if shots := list(presenter_path.glob(f"{slugify(row.get('Name'))}.*")):
                    default_profile_pic = f"/static/img/presenters/{shots[0].name}"
                else:
                    default_profile_pic = None
            post = frontmatter.loads(row.get("Biography") or "")
            data = Presenter(
                company=row.get("Organization or Affiliation", ""),
                # github: Optional[str]
                hidden=False,
                layout="speaker-template",
                name=row.get("Name"),
                # override_schedule_title: Optional[str] = None
                photo_url=default_profile_pic or row.get("Picture", ""),
                # role: Optional[str]
                # title: Optional[str]
                twitter=row.get("Twitter handle", ""),
                website=row.get("URL", ""),
                # website_text: str = "Apply here"
            )
            post.metadata.update(data.dict(exclude_unset=True))

            if output_folder is not None:
                output_path: Path = (
                    output_folder / POST_TYPES[-2]["path"] / f"{slugify(data.name)}.md"
                )
                output_path.write_text(frontmatter.dumps(post) + "\n")

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
            try:
                data = Schedule(
                    abstract=row["Abstract"],
                    accepted=True
                    if proposal_state in {"accepted", "confirmed"}
                    else False,
                    category=TALK_FORMATS[talk_format],
                    # post["difficulty"] = submission["talk"]["audience_level"],
                    layout="session-details",
                    permalink=f"/{TALK_FORMATS[talk_format]}/{talk_title_slug}/",
                    published=True,
                    sitemap=True,
                    slug=talk_title_slug,
                    tags=row["Tags"],
                    title=row["Proposal title"],
                    presenter_slugs=[slugify(name) for name in row["Speaker names"]],
                    room=row["Room"]["en"],
                    track=TRACKS.get(row["Room"]["en"], "t0"),
                    date=start_date,
                    end_date=end_date,
                    summary="",
                    # todo: refactor template layout to support multiple authors,
                    # presenters=row["Speaker names"],
                )

                post.metadata.update(data.dict(exclude_unset=True))

                if output_folder is not None:
                    output_path: Path = (
                        output_folder / POST_TYPES[-1]["path"] / data.category
                        # TODO please make this less ugly
                        / f"{data.date.year}-{data.date.month:0>2}-{data.date.day:0>2}-"
                        f"{data.date.hour:0>2}-{data.date.minute:0>2}-{data.track}-{data.slug}.md"
                    )
                    output_path.write_text(frontmatter.dumps(post))

            except ValidationError as e:
                print(f"[red]{row}[/red]")
                print(e.json())

            except Exception as e:
                print(f"[red]{e}[/red]")
                print(row)


if __name__ == "__main__":
    app()
