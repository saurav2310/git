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
    else:
        print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    main()