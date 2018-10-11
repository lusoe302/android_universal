#!/system/bin/sh

# get writable ramdisk
mount -o rw,remount /
# move everything prepared from /data/local/tmp
chmod 0750 /data/local/tmp/*
cp /data/local/tmp/* /sbin

# create symlink from /data/local/tmp -> /sbin, so frida_server will be happy
rm -rf /data/local/tmp
ln -s /sbin/ /data/local/tmp

# fire frida_server
/sbin/frida_server&

# now create a new tmp dir to upload/download files, if you need to
mkdir /data/local/samdisk
chown shell:shell /data/local/samdisk
chcon -h u:object_r:shell_data_file:s0 /data/local/samdisk
