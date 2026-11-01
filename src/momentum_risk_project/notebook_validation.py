"""Optional executed display/API validation, never the source of official results."""
from pathlib import Path
import nbformat
from nbclient import NotebookClient
from .paths import project_root


def main():
    root=project_root()
    for path in sorted((root/"notebooks").glob("0[1-5]*.ipynb")):
        notebook=nbformat.read(path,as_version=4)
        NotebookClient(notebook,timeout=300,kernel_name="python3",resources={"metadata":{"path":str(root)}}).execute()
        nbformat.write(notebook,path)
        print("Validated notebook: "+path.name,flush=True)

if __name__=="__main__":main()
