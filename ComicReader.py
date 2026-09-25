from komicove_app.auth_views import AuthWindow
from komicove_app.community_views import CommunityWindow
from komicove_app.moderation_views import ModerationWindow
from komicove_app.publishing_views import PublishDialog
from komicove_app.library_views import LibraryWindow
from komicove_app.reader_views import LangWindow, ReaderWindow, WebtoonViewer

__all__ = [
    "AuthWindow", "CommunityWindow", "LangWindow", "LibraryWindow",
    "ModerationWindow", "PublishDialog", "ReaderWindow", "WebtoonViewer",
]

if __name__ == "__main__":
    app = LibraryWindow()
    app.mainloop()
