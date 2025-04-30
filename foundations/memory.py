from numpy.ma.core import outer
from pydantic import BaseModel
import typing


class MemoryEntry(BaseModel):
    """
    Represents a single text entry in a memory section.

    Attributes:
        text (str): The textual content of the memory entry.
    """
    text: str


class MemorySection(BaseModel):
    """
    Represents a named section of memory, containing multiple entries.

    Attributes:
        name (str): The name of the memory section.
        entries (List[MemoryEntry]): List of memory entries in this section.
    """
    name: str
    entries: typing.List[MemoryEntry]


class Memory(BaseModel):
    """
    Represents the memory storage, organized into sections with entries.

    Attributes:
        sections (List[MemorySection]): List of named memory sections.
    """
    sections: typing.List[MemorySection] = []

    def add_entry(self, section_name: str, entry_text: str):
        """
        Adds a new entry to the specified section of memory. If the section does not exist,
        it is created.

        Args:
            section_name (str): Name of the section to add the entry to.
            entry_text (str): Text content of the memory entry.
        """
        for section in self.sections:
            if section.name == section_name:
                section.entries.append(MemoryEntry(text=entry_text))
                return

        # Create a new section if one doesn't exist yet
        self.sections.append(
            MemorySection(name=section_name, entries=[MemoryEntry(text=entry_text)])
        )

    def get_entry(self, section_name: str) -> str or None:
        """
        Retrieves the first entry from the specified section of memory.

        Args:
            section_name (str): Name of the section to retrieve the entry from.

        Returns:
            MemoryEntry: The first entry in the specified section, or None if not found.
        """
        for section in self.sections:
            if section.name == section_name and section.entries:
                return "\n".join(entry.text for entry in section.entries)
        return None

    def __str__(self):
        """
        Returns a human-readable string representation of the memory,
        grouping entries under their respective section names.

        Returns:
            str: Formatted memory string.
        """
        return "\n\n".join(
            [
                f"{section.name}\n\n" +
                "\n".join(entry.text for entry in section.entries)
                for section in self.sections
            ]
        )


# Demo usage if run as a standalone script
if __name__ == '__main__':
    memory = Memory()

    # Add Python-related facts
    memory.add_entry("Python", "Python is a programming language.")
    memory.add_entry("Python", "Python was created by Guido van Rossum.")
    memory.add_entry("Python", "Python is easy to learn.")
    memory.add_entry("Python", "Python is versatile.")

    # Add JavaScript-related facts
    memory.add_entry("JavaScript", "JavaScript is a scripting language.")
    memory.add_entry("JavaScript", "JavaScript is used for web development.")
    memory.add_entry("JavaScript", "JavaScript is an interpreted language.")
    memory.add_entry("JavaScript", "JavaScript is a high-level language.")

    # Print the structured memory
    print(memory.get_entry("Python"))