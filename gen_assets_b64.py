import base64

def get_b64(fn):
    with open(f'd:\\Projetos\\orca-cubic\\assets\\{fn}', 'rb') as f:
        return base64.b64encode(f.read()).decode('ascii')

thumb_b64 = get_b64('active_print_thumb.webp')
kobra_x_b64 = get_b64('kobra_x_thumb.webp')
kobra_2_plus_b64 = get_b64('kobra_2_plus_thumb.webp')

with open(r'd:\Projetos\orca-cubic\assets_b64.py', 'w', encoding='utf-8') as f:
    f.write(f'# Generated Base64 image assets for Anycubic Cloud Workbench\n')
    f.write(f'ACTIVE_PRINT_THUMB = "data:image/webp;base64,{thumb_b64}"\n\n')
    f.write(f'KOBRA_X_THUMB = "data:image/webp;base64,{kobra_x_b64}"\n\n')
    f.write(f'KOBRA_2_PLUS_THUMB = "data:image/webp;base64,{kobra_2_plus_b64}"\n')

print("Generated assets_b64.py successfully")
