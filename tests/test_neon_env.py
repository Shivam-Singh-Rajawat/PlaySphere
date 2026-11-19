"""Regression tests for Neon CLI environment-loading precedence and isolation."""
import os

import app


def test_neon_local_env_is_available_without_overriding_process_env(tmp_path, monkeypatch):
    (tmp_path / '.env').write_text('DATABASE_URL=sqlite:///old.db\nPLAYSPHERE_SECRET_KEY=from-env\n', encoding='utf-8')
    (tmp_path / '.env.local').write_text('DATABASE_URL=sqlite:///neon-cli.db\n', encoding='utf-8')
    tracked = ('DATABASE_URL', 'PLAYSPHERE_SECRET_KEY')
    before = {key: os.environ.get(key) for key in tracked}
    try:
        monkeypatch.delenv('DATABASE_URL', raising=False)
        monkeypatch.delenv('PLAYSPHERE_SECRET_KEY', raising=False)
        monkeypatch.delenv('VERCEL', raising=False)
        app.load_local_env(tmp_path)
        assert os.environ['DATABASE_URL'] == 'sqlite:///neon-cli.db'
        assert os.environ['PLAYSPHERE_SECRET_KEY'] == 'from-env'
        monkeypatch.setenv('DATABASE_URL', 'sqlite:///explicit-process.db')
        app.load_local_env(tmp_path)
        assert os.environ['DATABASE_URL'] == 'sqlite:///explicit-process.db'
    finally:
        for key, value in before.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_serverless_does_not_load_local_credential_files(tmp_path, monkeypatch):
    (tmp_path / '.env.local').write_text('DATABASE_URL=sqlite:///must-not-load.db\n', encoding='utf-8')
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('VERCEL', '1')
    app.load_local_env(tmp_path)
    assert 'DATABASE_URL' not in os.environ
