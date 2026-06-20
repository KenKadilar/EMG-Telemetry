#include <linux/module.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/fs.h>
#include <linux/miscdevice.h>
#include <linux/uaccess.h>
#include <linux/mutex.h>

#define EMG_BUF_SIZE 32

static char emgBuffer[EMG_BUF_SIZE];
static size_t emgDataLength;
static DEFINE_MUTEX(emgLock);

static int emgOpen(struct inode *inode, struct file *file)
{
    pr_info("emgactivity: device opened\n");
    return 0;
}

static int emgRelease(struct inode *inode, struct file *file)
{
    pr_info("emgactivity: device closed\n");
    return 0;
}

static ssize_t emgRead(struct file *file, char __user *userBuffer, size_t length, loff_t *offset)
{
    size_t remaining;
    size_t toCopy;
    ssize_t result;

    mutex_lock(&emgLock);

    if (*offset >= emgDataLength) {
        result = 0;
    } else {
        remaining = emgDataLength - *offset;
        if (remaining > length)
        {
            toCopy = length;
        }
        else
        {
            toCopy = remaining;
        }

        if (copy_to_user(userBuffer, emgBuffer + *offset, toCopy)) {
            result = -EFAULT;
        } else {
            *offset += toCopy;
            result = toCopy;
        }
    }

    mutex_unlock(&emgLock);
    return result;
}

static ssize_t emgWrite(struct file *file, const char __user *userBuffer, size_t length, loff_t *offset)
{
    size_t writeLength = length;

    if (writeLength > EMG_BUF_SIZE - 1) {
        writeLength = EMG_BUF_SIZE - 1;
    }

    mutex_lock(&emgLock);

    if (copy_from_user(emgBuffer, userBuffer, writeLength)) {
        mutex_unlock(&emgLock);
        return -EFAULT;
    }
    emgBuffer[writeLength] = '\0';
    emgDataLength = writeLength;

    mutex_unlock(&emgLock);

    return length;
}

static const struct file_operations emgFops = {
    .owner = THIS_MODULE,
    .open = emgOpen,
    .release = emgRelease,
    .read = emgRead,
    .write = emgWrite,
};

static struct miscdevice emgMisc = {
    .minor = MISC_DYNAMIC_MINOR,
    .name = "emgactivity",
    .fops = &emgFops,
    .mode = 0666,
};

static int __init emgActivityInit(void)
{
    int result;

    strscpy(emgBuffer, "0\n", EMG_BUF_SIZE);
    emgDataLength = 2;

    result = misc_register(&emgMisc);
    if (result < 0) {
        pr_err("emgactivity: failed to register misc device\n");
        return result;
    }
    pr_info("emgactivity: module loaded, /dev/emgactivity ready\n");
    return 0;
}

static void __exit emgActivityExit(void)
{
    misc_deregister(&emgMisc);
    pr_info("emgactivity: module unloaded\n");
}

module_init(emgActivityInit);
module_exit(emgActivityExit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Ken Kadilar");
MODULE_DESCRIPTION("EMG activity level character device");
