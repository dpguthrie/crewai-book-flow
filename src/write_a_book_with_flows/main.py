#!/usr/bin/env python
import asyncio
import os
from typing import List

# Load environment variables first
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from crewai.flow.flow import Flow, listen, start
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
from pydantic import BaseModel

from write_a_book_with_flows.crews.outline_book_crew.outline_crew import OutlineCrew
from write_a_book_with_flows.crews.write_book_chapter_crew.write_book_chapter_crew import (
    WriteBookChapterCrew,
)
from write_a_book_with_flows.instrumentation import get_instrumentor
from write_a_book_with_flows.types import Chapter, ChapterOutline

# Initialize and instrument CrewAI with Braintrust tracing
instrumentor = get_instrumentor()
instrumentor.instrument()

# Instrument OpenAI calls with the same tracer provider
OpenAIInstrumentor().instrument(tracer_provider=instrumentor.tracer_provider)


class BookState(BaseModel):
    id: str = "1"
    title: str = "The Current State of AI in July 2025"
    book: List[Chapter] = []
    book_outline: List[ChapterOutline] = []
    topic: str = (
        "Exploring the latest trends in AI across different industries as of July 2025"
    )
    goal: str = """
        The goal of this book is to provide an overview of the current state of artificial intelligence in July 2025.
        It will delve into the latest trends impacting various industries, analyze significant advancements,
        and discuss potential future developments. The book aims to inform readers about cutting-edge AI technologies
        and prepare them for upcoming innovations in the field in less than or equal to 2 chapters.
    """


class BookFlow(Flow[BookState]):
    initial_state = BookState

    @start()
    def generate_book_outline(self):
        print("Kickoff the Book Outline Crew")
        output = (
            OutlineCrew()
            .crew()
            .kickoff(inputs={"topic": self.state.topic, "goal": self.state.goal})
        )

        chapters = output["chapters"]
        print("Chapters:", chapters)

        self.state.book_outline = chapters
        return chapters

    @listen(generate_book_outline)
    async def write_chapters(self):
        print("Writing Book Chapters")
        tasks = []

        async def write_single_chapter(chapter_outline):
            output = (
                WriteBookChapterCrew()
                .crew()
                .kickoff(
                    inputs={
                        "goal": self.state.goal,
                        "topic": self.state.topic,
                        "chapter_title": chapter_outline.title,
                        "chapter_description": chapter_outline.description,
                        "book_outline": [
                            chapter_outline.model_dump_json()
                            for chapter_outline in self.state.book_outline
                        ],
                    }
                )
            )
            title = output["title"]
            content = output["content"]
            chapter = Chapter(title=title, content=content)
            return chapter

        for chapter_outline in self.state.book_outline:
            print(f"Writing Chapter: {chapter_outline.title}")
            print(f"Description: {chapter_outline.description}")
            # Schedule each chapter writing task
            task = asyncio.create_task(write_single_chapter(chapter_outline))
            tasks.append(task)

        # Await all chapter writing tasks concurrently
        chapters = await asyncio.gather(*tasks)
        print("Newly generated chapters:", chapters)
        self.state.book.extend(chapters)

        print("Book Chapters", self.state.book)

    @listen(write_chapters)
    async def join_and_save_chapter(self):
        print("Joining and Saving Book Chapters")
        # Combine all chapters into a single markdown string
        book_content = ""

        for chapter in self.state.book:
            # Add the chapter title as an H1 heading
            book_content += f"# {chapter.title}\n\n"
            # Add the chapter content
            book_content += f"{chapter.content}\n\n"

        # The title of the book from self.state.title
        book_title = self.state.title

        # Create the filename by replacing spaces with underscores and adding .md extension
        filename = f"./{book_title.replace(' ', '_')}.md"

        # Save the combined content into the file
        with open(filename, "w", encoding="utf-8") as file:
            file.write(book_content)

        print(f"Book saved as {filename}")
        return book_content


def kickoff():
    # Get environment from env var, default to 'DEV' if not set
    ENVIRONMENT = os.environ.get("ENVIRONMENT", "DEV")

    print(f"Starting BookFlow in {ENVIRONMENT} environment")

    poem_flow = BookFlow()
    poem_flow.kickoff()

    return poem_flow


def plot():
    poem_flow = BookFlow()
    poem_flow.plot()


if __name__ == "__main__":
    kickoff()
