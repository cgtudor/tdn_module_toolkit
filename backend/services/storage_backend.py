"""Storage backend protocol for GFF resource I/O."""
from typing import Protocol, Optional, List, runtime_checkable


@runtime_checkable
class GFFStorageBackend(Protocol):
    """Protocol defining the storage interface for GFF resources.

    Backends implement this to provide read/write access to NWN module
    resources (UTI, UTC, UTM, GIT, ARE, ITP, etc.) regardless of
    whether they live as JSON files on disk or inside a .mod container.
    """

    def list_resources(self, resource_type: str) -> List[str]:
        """List all resrefs of a given resource type.

        Args:
            resource_type: The resource type extension (e.g., 'uti', 'utc',
                'utm', 'git', 'are', 'itp').

        Returns:
            List of resref strings (without extensions).
        """
        ...

    def read_resource(self, resref: str, resource_type: str) -> Optional[dict]:
        """Read a resource and return its data as a dict.

        Args:
            resref: The resource reference name.
            resource_type: The resource type extension.

        Returns:
            The resource data as a dict, or None if not found or unreadable.
        """
        ...

    def write_resource(self, resref: str, resource_type: str, data: dict) -> bool:
        """Write resource data.

        Args:
            resref: The resource reference name.
            resource_type: The resource type extension.
            data: The resource data dict to write.

        Returns:
            True if the write succeeded, False otherwise.
        """
        ...

    def resource_exists(self, resref: str, resource_type: str) -> bool:
        """Check whether a resource exists.

        Args:
            resref: The resource reference name.
            resource_type: The resource type extension.

        Returns:
            True if the resource exists.
        """
        ...

    def delete_resource(self, resref: str, resource_type: str) -> bool:
        """Delete a resource.

        Args:
            resref: The resource reference name.
            resource_type: The resource type extension.

        Returns:
            True if the resource was deleted, False if it didn't exist
            or deletion failed.
        """
        ...

    def rename_resource(self, old_resref: str, new_resref: str, resource_type: str) -> bool:
        """Rename a resource at the storage level.

        This performs only a storage-level rename (move/copy the underlying
        data). It does NOT modify dict contents such as TemplateResRef --
        that is the caller's responsibility.

        Args:
            old_resref: Current resource reference name.
            new_resref: New resource reference name.
            resource_type: The resource type extension.

        Returns:
            True if the rename succeeded, False otherwise.
        """
        ...

    def get_resource_modified(self, resref: str, resource_type: str) -> str:
        """Get a modification indicator for change detection.

        For file-based backends this is typically the file mtime as an
        ISO-format string. For in-memory backends it could be a content
        hash or version counter.

        Args:
            resref: The resource reference name.
            resource_type: The resource type extension.

        Returns:
            A string representing the current version/mtime, or empty
            string if the resource doesn't exist.
        """
        ...

    def get_mode(self) -> str:
        """Return the backend mode identifier.

        Returns:
            'json_directory' for the JSON file backend,
            'mod_file' for the MOD container backend.
        """
        ...
