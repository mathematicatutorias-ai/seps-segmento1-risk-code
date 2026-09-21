from pathlib import Path
import yaml


def test_academic_disclaimer_is_configured_and_visible():
    root=Path(__file__).resolve().parents[1]
    cfg=yaml.safe_load((root/'config/project.yaml').read_text(encoding='utf-8'))
    pub=cfg['publication']
    assert pub.get('academic_use') is True
    assert 'académico' in pub.get('academic_notice','').lower()
    assert 'recomendación financiera' in pub.get('disclaimer','').lower()
    template=(root/'src/sepsrisk/reporting/index_template.html').read_text(encoding='utf-8')
    app=(root/'githubpage/assets/app.js').read_text(encoding='utf-8')
    assert 'id="academicNotice"' in template
    assert 'renderAcademicNotice' in app
