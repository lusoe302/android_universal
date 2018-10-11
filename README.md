# Android Universal Boot Rooting Toolkit 
(c) B. Kerler, MIT License

Converts stock boot images and adds hidden root (accessible via netcat session), patches selinux and adds adb. 
Tested with Android 4.x - 8.x.

## Options:

  -filename FILENAME, -fn FILENAME
                        boot.img or recovery.img
  -justunpack, -ju      Just extract kernel + ramdisk
  -custom, -c           Stop in order to make changes
  -precustom, -pc       Stop in order to make changes before patches
  
## Usage:

### Linux:
```
./makeramdisk.sh -filename boot.img
```

### Windows:
```
./makeramdisk.cmd -filename boot.img
```

## ToDo:
Nothing, but maybe Android 9 needs more help :)
