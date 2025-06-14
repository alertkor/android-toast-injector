import getpass
import glob
import json
import os
import re
import sys


class AndroidToastInject:
    def __init__(self):
        if len(sys.argv) <= 1:
            print('[-] Error: Input xapk or apk path.')
            print('$ python main.py test.apk')
            exit()
        elif not sys.argv[1].endswith('apk') and not sys.argv[1].endswith('xapk'):
            print('[-] Error: unknown extension.')
            exit()
        elif not os.path.exists(sys.argv[1]):
            print('[-] Error: target not found.')
            exit()

        self.toast_msg = sys.argv[2] if len(sys.argv) > 2 else 'Hello, Repackaging works!'
        self.main_activity_path = ''
        self.min_sdk_version = 28
        self.package_name = ''
        self._target_apk_path = sys.argv[1]
        self.is_xapk = self._target_apk_path.endswith('.xapk')
        self.decompile()
        self.find_main_activity()
        self.inject_toast()
        self.compile()
        self.key_generate()
        self.signing()
        self.remove()
        return

    def __log(self, msg):
        print(f'{msg}')
        return

    def decompile(self):
        self.__log('[*] Decompiling...')
        os.system(f"apktool d {sys.argv[1]} -o output -f -r")
        if self.is_xapk:
            manifest = json.loads(open('./output/unknown/manifest.json', 'r').read())
            self.package_name = manifest['package_name']
            self.min_sdk_version = manifest.get('min_sdk_version', 28)
            os.system(f"apktool d ./output/unknown/{self.package_name}.apk -o ./output/unknown/{self.package_name} -f -r")
        else:
            apktool = open('./output/apktool.yml', 'r').read()
            self.min_sdk_version = re.findall('minSdkVersion: \'(.*?)\'\n', apktool)[0] or 28
        return

    def find_main_activity(self):
        self.__log('[*] Finding MainActivity.smali...')
        if self.is_xapk:
            self.main_activity_path = os.popen(f'find ./output/unknown/{self.package_name}/smali* -name MainActivity.smali').read().strip()
        else:
            self.main_activity_path = os.popen('find ./output/smali* -name MainActivity.smali').read().strip()

        if self.main_activity_path:
            self.__log(f'[+] MainActivity found: {self.main_activity_path}')
        else:
            self.__log('[-] Failed to find MainActivity.smali')
            exit()
        return

    def inject_toast(self):
        self.__log('[*] Inject toast message...')
        on_create_line = 0
        smali_lines = open(self.main_activity_path, 'r').readlines()
        find_target = 'onCreate(Landroid/os/Bundle;)V'.lower()
        for idx, line in enumerate(smali_lines):
            if line.lower().__contains__(find_target):
                on_create_line = idx
                break

        local_variable = smali_lines[on_create_line + 1]
        modify_local_variable = str(local_variable.split(' ')[-1])
        smali_lines[on_create_line + 1] = smali_lines[on_create_line + 1] \
            .replace(modify_local_variable, str(int(modify_local_variable) + 2))

        inject_smali = [
            f'\nconst-string v0, "{self.toast_msg}"\n',
            'const/4 v1, 0x0\n',
            'invoke-static {p0, v0, v1}, Landroid/widget/Toast;->makeText(Landroid/content/Context;Ljava/lang/CharSequence;I)Landroid/widget/Toast;\n',
            'move-result-object v0\n',
            'invoke-virtual {v0}, Landroid/widget/Toast;->show()V\n\n',
        ]

        smali_lines = smali_lines[:on_create_line + 2] + inject_smali + smali_lines[on_create_line + 2:]
        open(self.main_activity_path, 'w').write(''.join(smali_lines))
        self.__log('[*] Successfully injected.')
        return

    def compile(self):
        self.__log('[*] Compiling...')
        if self.is_xapk:
            os.system(f'apktool b --use-aapt2 ./output/unknown/{self.package_name} -o ./output/unknown/{self.package_name}.apk')
        else:
            os.system('apktool b --use-aapt2 output -o patched.apk')
        return

    def key_generate(self):
        self.__log('[*] Generate keystore...')
        if not os.path.exists('injector.keystore'):
            os.system('keytool -genkey -v -keystore injector.keystore -alias injector_alias -keyalg RSA -validity 10000')
        return

    def signing(self):
        self.__log('[*] Signing...')
        password = getpass.getpass('[*] Input your key password: ')
        if self.is_xapk:
            total_size = 0
            for split_apk in glob.glob('./output/unknown/*.apk'):
                os.system(f'apksigner sign --ks injector.keystore --min-sdk-version {self.min_sdk_version} --ks-pass pass:"{password}" {split_apk}')
                total_size += len(open(split_apk, 'rb').read())
                self.__log(f'[+] Successfully signed in {split_apk}')
            manifest = json.loads(open('./output/unknown/manifest.json', 'r').read())
            manifest['total_size'] = total_size
            open('./output/unknown/manifest.json', 'w').write(json.dumps(manifest, ensure_ascii=False))
            os.system(f'apktool b --use-aapt2 output -o patched.xapk')
            os.system(f'apksigner sign --ks injector.keystore --min-sdk-version {self.min_sdk_version} --ks-pass pass:"{password}" patched.xapk')
        else:
            os.system(f'apksigner sign --ks injector.keystore --min-sdk-version {self.min_sdk_version} --ks-pass pass:"{password}" patched.apk')
        return

    def remove(self):
        self.__log('[*] Remove decompiled files...')
        os.system('rm -rf ./output/')
        self.__log(f'[*] Successfully generated: patched.{"xapk" if self.is_xapk else "apk"}')
        return


if __name__ == '__main__':
    AndroidToastInject()
