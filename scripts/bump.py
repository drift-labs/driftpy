import re
import os


def bump_version(version):
    major, minor, patch = map(int, version.split("."))
    patch += 1
    return f"{major}.{minor}.{patch}"


def update_file(file_path, pattern, replacement):
    with open(file_path, "r") as file:
        content = file.read()

    updated_content = re.sub(pattern, replacement, content)

    with open(file_path, "w") as file:
        file.write(updated_content)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    pyproject_path = os.path.join(project_root, "pyproject.toml")
    pyproject_pattern = r'(version\s*=\s*["\'])(\d+\.\d+\.\d+)(["\'])'

    init_path = os.path.join(project_root, "src", "driftpy", "__init__.py")
    init_pattern = r'(__version__\s*=\s*["\'])(\d+\.\d+\.\d+)(["\'])'

    bumpversion_path = os.path.join(project_root, ".bumpversion.cfg")
    bumpversion_pattern = r"(current_version\s*=\s*)(\d+\.\d+\.\d+)"

    with open(pyproject_path, "r") as file:
        content = file.read()
        match = re.search(pyproject_pattern, content)
        if match:
            current_version = match.group(2)
        else:
            print("Couldn't find version in pyproject.toml")
            return

    new_version = bump_version(current_version)

    update_file(pyproject_path, pyproject_pattern, rf"\g<1>{new_version}\g<3>")
    update_file(init_path, init_pattern, rf"\g<1>{new_version}\g<3>")
    update_file(bumpversion_path, bumpversion_pattern, rf"\g<1>{new_version}")

    print(f"Version bumped from {current_version} to {new_version}")


if __name__ == "__main__":
    main()
