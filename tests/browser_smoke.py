"""Optional Chromium smoke test, bridged directly to the real FastAPI TestClient.
Run: python tests/browser_smoke.py (requires playwright and installed Chromium).
"""
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import create_app


def main():
    with TemporaryDirectory(prefix='playsphere-browser-') as temp:
        app = create_app(database_url=f'sqlite:///{Path(temp) / "test.db"}', upload_dir=Path(temp) / 'uploads')
        with TestClient(app) as client, sync_playwright() as pw:
            browser_kwargs = {'headless': True, 'args': ['--no-sandbox']}
            binary = shutil.which('chromium') or shutil.which('chrome')
            if binary:
                browser_kwargs['executable_path'] = binary
            browser = pw.chromium.launch(**browser_kwargs)
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))

            def api_bridge(path, method, headers, body):
                res = client.request(method, path, headers=headers, content=body.encode() if body else None)
                return {'status': res.status_code, 'body': res.text}

            page.expose_function('requestApi', api_bridge)
            html = (ROOT / 'web/index.html').read_text(encoding='utf-8')
            html = html.replace('<script src="/assets/app.js" defer></script>', '')
            html = html.replace('<link rel="stylesheet" href="/assets/style.css">',
                                '<style>' + (ROOT / 'web/style.css').read_text(encoding='utf-8') + '</style>')
            page.set_content(html, wait_until='domcontentloaded')
            page.evaluate("""(()=>{Object.defineProperty(window,'sessionStorage',
                {value:{getItem:()=>null,setItem:()=>{},removeItem:()=>{}},configurable:true});
                window.fetch=async(path,o={})=>{const r=await window.requestApi(path,o.method||'GET',o.headers||{},o.body||'');
                return {ok:r.status>=200&&r.status<300,status:r.status,json:async()=>JSON.parse(r.body)}};
                return true;})()""")
            page.add_script_tag(content=(ROOT / 'web/app.js').read_text(encoding='utf-8'))
            expect(page.locator('#players-grid')).not_to_contain_text('Loading players')

            def register(role, email):
                page.locator('#nav-actions [data-action="register"]').click()
                form = page.locator('[data-form="register"]')
                for name, value in {'name': 'Jordan Lee' if role == 'player' else 'Coach Ellis',
                                    'email': email, 'password': 'StrongPass!1234'}.items():
                    form.locator(f'[name="{name}"]').fill(value)
                form.locator('[name="role"]').select_option(role)
                form.locator('button[type="submit"]').click()
                expect(page.locator('#modal-shell')).to_be_hidden(timeout=12000)

            def login(email):
                page.locator('#nav-actions [data-action="login"]').click()
                form = page.locator('[data-form="login"]')
                form.locator('[name="email"]').fill(email)
                form.locator('[name="password"]').fill('StrongPass!1234')
                form.locator('button[type="submit"]').click()
                expect(page.locator('#modal-shell')).to_be_hidden(timeout=12000)

            def logout():
                page.locator('#nav-actions [data-action="logout"]').click()
                expect(page.locator('#my-space')).to_be_hidden()

            register('player', 'jordan@example.org')
            page.locator('#my-space [data-action="edit-profile"]').first.click()
            profile = page.locator('[data-form="profile"]')
            profile.locator('[name="position"]').fill('Striker')
            profile.locator('[name="city"]').fill('Dehradun')
            profile.locator('button[type="submit"]').click()
            expect(page.locator('#modal-shell')).to_be_hidden(timeout=12000)
            page.locator('#my-space [data-action="add-achievement"]').first.click()
            form = page.locator('[data-form="achievement"]')
            form.locator('[name="title"]').fill('District Finals MVP')
            form.locator('[name="issuer"]').fill('Local Sports Board')
            form.locator('[name="evidence_url"]').fill('https://example.org/award')
            form.locator('button[type="submit"]').click()
            expect(page.locator('#my-space')).to_contain_text('District Finals MVP', timeout=12000)
            page.locator('#my-space [data-action="add-video"]').first.click()
            form = page.locator('[data-form="video"]')
            form.locator('[name="title"]').fill('Match Highlights')
            form.locator('[name="url"]').fill('https://www.youtube.com/watch?v=example123')
            form.locator('button[type="submit"]').click()
            expect(page.locator('#my-space')).to_contain_text('Match Highlights', timeout=12000)
            print('PASS player profile, achievements, video link')

            logout()
            register('coach', 'ellis@example.org')
            page.locator('#my-space [data-action="create-tournament"]').click()
            form = page.locator('[data-form="tournament"]')
            form.locator('[name="title"]').fill('City Youth Challenge')
            form.locator('[name="location"]').fill('Dehradun Arena')
            form.locator('button[type="submit"]').click()
            expect(page.locator('#tournaments-list')).to_contain_text('City Youth Challenge', timeout=12000)
            page.locator('#players-grid [data-action="view-player"]').first.click()
            expect(page.locator('#modal-content')).to_contain_text('District Finals MVP', timeout=12000)
            page.locator('#modal-content [data-action="evaluate"]').click()
            form = page.locator('[data-form="evaluate"]')
            form.locator('[name="technique"]').select_option('5')
            form.locator('[name="notes"]').fill('Strong finishing')
            form.locator('button[type="submit"]').click()
            page.locator('#my-space [data-action="evaluate"]').first.click()
            expect(page.locator('[data-form="evaluate"] [name="notes"]')).to_have_value('Strong finishing')
            page.locator('#modal-shell [data-action="close-modal"]').last.click()
            print('PASS tournament publishing, saved scout evaluation and edit')

            logout()
            login('jordan@example.org')
            page.locator('#tournaments-list [data-action="join-tournament"]').first.click()
            expect(page.locator('#my-space')).to_contain_text('City Youth Challenge', timeout=12000)
            logout()
            login('ellis@example.org')
            page.locator('#my-space [data-action="view-registrations"]').first.click()
            expect(page.locator('#modal-content')).to_contain_text('Jordan Lee', timeout=12000)
            page.locator('#modal-shell [data-action="close-modal"]').last.click()
            page.set_viewport_size({'width': 390, 'height': 844})
            expect(page.locator('#main-nav')).to_be_attached()
            assert not errors, errors
            print('PASS registrations, private organizer roster, mobile DOM and zero JS errors')
            browser.close()


if __name__ == '__main__':
    main()
