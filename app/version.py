"""App version -- bump this as part of cutting each release (matching the
git tag, e.g. tag v1.0.7 -> __version__ = "1.0.7"). Used only to compare
against the latest GitHub release for the update-available notice; never
read from git at runtime since a frozen build has no .git directory."""

__version__ = "1.0.6"
