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
        
        #compute SHA-1
        sha1 = hashlib.sha1(store_data).hexdigest()



def main():
    if (len(sys.argv)<2):
        print("Usage: spvcs <command> [args]")
        return
    cmd = sys.argv[1]
    repo = SPVCS()

    if cmd == 'init':
        repo.init()
    else:
        print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    main()