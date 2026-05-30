#! usr/bin/env python3
import sys, os, hashlib, zlib
from pathlib import Path
from datetime import datetime

class SPVCS:
    def __init__(self,repo_path='.'):
        self.repo_path = Path(repo_path).absolute()
        self.spvcs_dir = self.repo_path / '.spvcs'

    def init(self):
        """ Create .spvcs directory and subdirectories """
        if self.spvcs_dir.exists():
            print("Repository already exists.")
            return
        # create objects/ and refs/heads/
        (self.spvcs_dir/'objects').mkdir(parents=True)
        (self.spvcs_dir/'refs'/'heads').mkdir(parents=True)
        with open(self.spvcs_dir/'HEAD','w') as f:
            f.write('ref: refs/heads/master\n')
        print(f"Initialized empty SPVCS repoository in {self.spvcs_dir}")
    
    def hash_object(self, data, obj_type='blob'):
        """ Store any data as an object and return its hash """
        # Format: <type><size>\0<content>
        header = f"{obj_type} {len(data)}\0".encode()
        store_data = header + data

        sha1 = hashlib.sha1(store_data).hexdigest()
        # Compress and store
        obj_path = self.spvcs_dir / 'objects' / sha1[:2] / sha1[2:]
        obj_path.parent.mkdir(parents=True,exist_ok=True)
        with open(obj_path, 'wb') as f:
            f.write(zlib.compress(store_data))
        return sha1

    def hash_obj_file(self, file_path):
        """ Read File and store as blob object """
        with open(file_path, 'rb') as f:
            data = f.read()
        return self.hash_object(data,'blob')
    
    def read_object(self, sha1):
        """Read and decompress object, return (type, data)"""
        obj_path = self.spvcs_dir / 'objects' / sha1[:2] /sha1[2:]
        if not obj_path.exists():
            raise FileNotFoundError(f"Object {sha1} not found")
        with open(obj_path, 'rb') as f:
            compressed_data = f.read()
        decompressed = zlib.decompress(compressed_data)

        null_index = decompressed.find(b'\0')
        header = decompressed[:null_index].decode()
        obj_type, str_size = header.split()
        size = int(str_size)
        data = decompressed[null_index+1:]
        assert len(data) == size, "Size mismatch in object data"
        return obj_type, data
    
    def write_tree(self,dirpath='.'):
        """Create Tree object from directory and return its hash"""
        entries = []
        full_dir = self.repo_path / dirpath
        for item in sorted(full_dir.iterdir()):
            if item.name == '.spvcs':
                continue
            if item.is_file():
                # blob
                with open(item,'rb') as f:
                    data = f.read()
                blob_hash = self.hash_object(data,'blob')
                mode = b'100644' # Regular File
                entry = mode + b' ' + item.name.encode() + b'\0' + bytes.fromhex(blob_hash)
                entries.append(entry)
            elif item.is_dir():
                subdir_rel = Path(dirpath)/item.name
                tree_hash = self.write_tree(str(subdir_rel))
                mode = b'40000'  # Directory File
                entry = mode + b' ' + item.name.encode() + b'\0' + bytes.fromhex(tree_hash)
                entries.append(entry)
        # Concatenate all entries
        tree_data = b''.join(entries)
        return self.hash_object(tree_data,'tree')
    
    def read_tree(self, tree_hash,target_dir='.'):
        """Restore the tree object into target Directory (Overwrite)"""
        obj_type, tree_data = self.read_object(tree_hash)
        if obj_type != 'tree':
            raise ValueError("Not a tree object")
        target = self.repo_path / target_dir
        target.mkdir(parents=True, exist_ok=True)

        i = 0
        while i < len(tree_data):
            space_idx = tree_data.find(b' ',i)
            mode = tree_data[i:space_idx].decode()
            null_idx = tree_data.find(b'\0',space_idx)
            name = tree_data[space_idx+1:null_idx].decode()
            raw_hash = tree_data[null_idx+1:null_idx+21]
            obj_hash = raw_hash.hex()

            i = null_idx + 21

            item_path = target / name
            if mode == '100644':
                _,content = self.read_object(obj_hash)
                with open(item_path, 'wb') as f:
                    f.write(content)
            elif mode =='40000':
                self.read_tree(obj_hash, str(Path(target_dir) / name))
            else:
                print(f"Unknown mode {mode} for {name}, skipping")
    def commit(self, message, parent=None):
        """Create a commit from current working tree"""
        tree_hash = self.write_tree()
        content = f"tree {tree_hash}\n"
        if parent:
            content += f"parent {parent}\n"
        name  = os.getenv('USER','unknown')
        email = f"{name} <{name}@example.com>"
        timestamp = int(datetime.now().timestamp())
        tz = "+0000"
        content += f"author {email} {timestamp} {tz}\n"
        content += f"committer {email} {timestamp} {tz}\n\n"
        content += f"\n{message}\n"

        commit_hash = self.hash_object(content.encode(),'commit')

        branch_path = self.spvcs_dir / 'refs' / 'heads' / 'master'
        with open(branch_path,'w') as f:
            f.write(commit_hash)
        print(f"Committed to master: {commit_hash}")
        return commit_hash
    def log(self):
        """Print commit history of current branch."""
        branch_path = self.spvcs_dir / 'refs' / 'heads' / 'master'
        if not branch_path.exists():
            print("No commits yet.")
            return
        with open(branch_path, 'r') as f:
            commit_hash = f.read().strip()
        while commit_hash:
            obj_type, content = self.read_object(commit_hash)
            if obj_type != 'commit':
                break
            # Parse commit lines
            lines = content.decode().split('\n')
            message = ''
            for line in lines:
                if line.startswith(' '):  # message line starts with space
                    message = line.strip()
                    break
            date_line = None
            for line in lines:
                if line.startswith('author'):
                    # "author Name <email> timestamp tz"
                    parts = line.split()
                    timestamp = int(parts[-2])
                    dt = datetime.fromtimestamp(timestamp)
                    date_line = dt.strftime('%a %b %d %H:%M:%S %Y')
                    break
            print(f"commit {commit_hash}")
            print(f"Date:   {date_line}")
            print(f"\n    {message}\n")
            # Find parent
            parent = None
            for line in lines:
                if line.startswith('parent '):
                    parent = line.split()[1]
                    break
            commit_hash = parent
    def checkout(self, commit_hash):
        """Replace working directory with the tree of given commit."""
        # Read commit object
        obj_type, commit_content = self.read_object(commit_hash)
        if obj_type != 'commit':
            raise ValueError("Not a commit object")
        # Extract tree hash from commit
        for line in commit_content.decode().split('\n'):
            if line.startswith('tree '):
                tree_hash = line.split()[1]
                break
        else:
            raise ValueError("Commit has no tree")
        # Restore tree (this will overwrite files)
        self.read_tree(tree_hash, '.')
        # Update HEAD and master branch (simple: we always checkout to master)
        branch_path = self.spvcs_dir / 'refs' / 'heads' / 'master'
        with open(branch_path, 'w') as f:
            f.write(commit_hash)
        print(f"Checked out commit {commit_hash[:7]}")



def main():
    if (len(sys.argv)<2):
        print("Usage: spvcs <command> [args]")
        return
    
    cmd = sys.argv[1]
    repo = SPVCS()

    if cmd == 'init':
        repo.init()
    
    elif cmd == 'hash-object':
        if(len(sys.argv)<3):
            print("Usage: spvcs hash-object <file>")
            return
        filepath = sys.argv[2]
        hash_val = repo.hash_obj_file(filepath)
        print(hash_val)
    
    elif cmd == 'cat-file':
        if(len(sys.argv)<3):
            print("Usage: spvcs cat-file <hash>")
            return
        obj_type,data = repo.read_object(sys.argv[2])
        sys.stdout.buffer.write(data)
    elif cmd == 'write-tree':
        tree_hash = repo.write_tree()
        print(tree_hash)
    elif cmd =='read-tree':
        if(len(sys.argv)<3):
            print("Usage: spvcs read-tree <tree-hash>")
            return
        repo.read_tree(sys.argv[2])
    elif cmd == 'commit':
        if len(sys.argv) < 4 or sys.argv[2] != '-m':
            print("Usage: spvcs commit -m <message>")
            return
        message = sys.argv[4]
        parent = None
        branch_path = repo.spvcs_dir / 'refs' / 'heads' / 'master'
        if branch_path.exists():
            with open(branch_path,'r') as f:
                parent = f.read().strip()
        repo.commit(message,parent)
    elif cmd == 'log':
        repo.log()
    elif cmd == 'checkout':
        if len(sys.argv) < 3:
            print("Usage: spvcs checkout <commit-hash>")
            return
        repo.checkout(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    main()