from komicove_app.launcher import main


def check_assets():
    import tkinter as tk
    from PIL import Image, ImageTk
    import komicove_app.runtime as runtime

    root = tk.Tk()
    root.withdraw()
    runtime.load_icons()
    logo = ImageTk.PhotoImage(Image.open(runtime.resource_path("komicovelogo.png")))
    missing = [name for name, icon in runtime.ICONS.items() if icon is None]
    root.destroy()
    if missing or not logo:
        raise SystemExit("Missing icons: " + ", ".join(missing))
    print("Komicove assets OK")


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--check-assets"]:
        check_assets()
    else:
        main()
