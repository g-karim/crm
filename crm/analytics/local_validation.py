"""Run the closed analytical fixture in a dedicated local site with rollback.

Uses one transaction. Existing rows are hashed before and after the run.
"""
import hashlib
import json
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import frappe

EVIDENCE = Path(__file__).resolve().parents[2] / '.pi/feats/analytics/evidence/2026-11-21'
SERVER_EVIDENCE = EVIDENCE.parent / '2026-11-22-rollup' / 'qa-site'


def run():
    if frappe.local.site != 'analytics-qa.localhost' or frappe.session.user != 'Administrator':
        raise RuntimeError('Run the closed fixture on analytics-qa.localhost as Administrator')
    if any(frappe.db.count(dt) for dt in ('CRM Lead', 'CRM Deal', 'CRM Task')):
        raise RuntimeError('The closed fixture requires a site without existing CRM business records')
    from crm.analytics import test_native, test_features, test_source_event_import
    from crm.analytics.testing import seed, clock

    protected = ['CRM Lead', 'CRM Deal', 'CRM Task', 'CRM Dashboard', 'User',
                 'CRM Deal Status', 'CRM Sales Pipeline', 'CRM Analytics Event',
                 'CRM Analytics Snapshot', 'ToDo', 'CRM Notification', 'FCRM Note', 'CRM Call Log', 'File']
    def signature():
        return {dt: hashlib.sha256(json.dumps(frappe.get_all(dt, fields=['*'],
                 order_by='name', limit_page_length=0), default=str, sort_keys=True).encode()).hexdigest()
                 for dt in protected}
    before = signature()
    previous_flag = frappe.flags.analytics_local_validation
    previous_test = frappe.flags.in_test
    frappe.flags.analytics_local_validation = True
    frappe.flags.in_test = True
    output = {'site': frappe.local.site, 'mode': 'transaction with mandatory rollback'}
    try:
        with ExitStack() as stack:
            stack.enter_context(patch.object(frappe.db, 'commit', side_effect=RuntimeError('Commit forbidden in analytics verification')))
            # Network providers are not used in this validation.
            stack.enter_context(patch('crm.fcrm.doctype.crm_deal.crm_deal.get_exchange_rate', return_value=1))
            manifest = seed(prefix='analytics-check-20261116', transactional=True)
            frappe.db.savepoint('analytics_fixture')
            def setup(case):
                frappe.set_user('Administrator')
                case.manifest = manifest
                case.timer = clock('2026-10-26 12:00:00')
                case.timer.__enter__()
            def teardown(case):
                case.timer.__exit__(None, None, None)
                frappe.set_user('Administrator')
                frappe.db.rollback(save_point='analytics_fixture')
                frappe.clear_cache()
            suite = unittest.TestSuite()
            skipped = {}
            for cls in [test_native.TestAnalyticsNative, test_features.TestAnalyticsFeatures]:
                stack.enter_context(patch.object(cls, 'setUp', setup))
                stack.enter_context(patch.object(cls, 'tearDown', teardown))
                for name in unittest.defaultTestLoader.getTestCaseNames(cls):
                    if name not in skipped: suite.addTest(cls(name))
            def setup_import(case):
                frappe.set_user('Administrator')
                case.timer = ExitStack()
                original_get = frappe.db.get_single_value
                case.timer.enter_context(patch.object(frappe.db, 'get_single_value', side_effect=lambda dt, field, *a, **kw:
                    'UTC' if (dt, field) == ('System Settings', 'time_zone') else original_get(dt, field, *a, **kw)))
                case.deal = manifest['deals']['D4']
                from crm.analytics.history import internal_write, EVENT
                from crm.analytics.source_event_import import parse_event
                sequence = frappe.db.count(EVENT, {'source_type': 'CRM Deal', 'source_name': case.deal})
                for number, stamp in [(20, '2026-10-26T11:00:00Z'), (22, '2026-10-26T13:00:00Z')]:
                    sequence += 1
                    event = parse_event('analytics-h05-feed', 'D4-source', f'evt-{number:03}', stamp)
                    with internal_write():
                        frappe.get_doc({'doctype':EVENT,'source_type':'CRM Deal','source_name':case.deal,
                            'sequence':sequence,'event_kind':'Updated','occurred_at':event.occurred_at,
                            'source_event_key':event.key(), 'actor':'Administrator',
                            'payload':json.dumps({'timezone':'UTC','source_event':event.payload()})}).insert(ignore_permissions=True, set_name='analytics-check-receipt-'+str(number))
                case.before = frappe.db.count(EVENT)
            def teardown_import(case):
                case.assertEqual(frappe.db.count('CRM Analytics Event'), case.before)
                case.timer.close()
                frappe.db.rollback(save_point='analytics_fixture')
                frappe.clear_cache()
            cls = test_source_event_import.TestSourceEventImport
            stack.enter_context(patch.object(cls, 'setUp', setup_import))
            stack.enter_context(patch.object(cls, 'tearDown', teardown_import))
            suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
            result = unittest.TextTestRunner(verbosity=1).run(suite)
            output.update(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                          excluded=skipped, successful=result.wasSuccessful())
    finally:
        frappe.db.rollback()
        frappe.set_user('Administrator')
        frappe.flags.analytics_local_validation = previous_flag
        frappe.flags.in_test = previous_test
        frappe.clear_cache()
        after = signature()
        output['protected_rows_unchanged'] = before == after
        output['changed_source_types'] = [dt for dt in before if before[dt] != after[dt]]
        output['before_signatures'] = before
        output['after_signatures'] = after
        frappe.db.rollback()
        SERVER_EVIDENCE.mkdir(parents=True, exist_ok=True)
        (SERVER_EVIDENCE / 'server-validation.json').write_text(json.dumps(output, indent=2))
    if not output['protected_rows_unchanged']:
        raise AssertionError('Protected source row signatures changed')
    if not output.get('successful'):
        raise AssertionError('Analytics scenario validation failed; see saved evidence')
    return output


def capture_preview():
    """Capture synthetic API results for visual QA only; never persist the fixture."""
    if frappe.local.site != 'analytics.localhost' or frappe.session.user != 'Administrator':
        raise RuntimeError('Local CRM only')
    from crm.analytics.testing import seed, clock
    from crm.analytics.test_native import FILTERS
    from crm.analytics.service import get_report, get_details
    from crm.analytics.summary import get_summary
    previous = frappe.flags.analytics_local_validation
    protected = ['CRM Lead','CRM Deal','CRM Task','CRM Dashboard','User','CRM Analytics Event','CRM Analytics Snapshot','ToDo']
    def signature():
        return {dt: hashlib.sha256(json.dumps(frappe.get_all(dt, fields=['*'], order_by='name', limit_page_length=0),default=str,sort_keys=True).encode()).hexdigest() for dt in protected}
    before = signature()
    try:
        frappe.flags.analytics_local_validation = True
        with patch.object(frappe.db,'commit',side_effect=RuntimeError('Preview must roll back')):
            seed(prefix='analytics-preview-20261116',transactional=True)
            with clock('2026-10-26 12:00:00'):
                report = get_report(FILTERS)
                details = {key:get_details(report['snapshot_token'],key) for key in ['new_leads','won_value','forecast','risk_count']}
                summary = get_summary(report['snapshot_token'])
                report['snapshot_token'] = 'synthetic-visual-qa-only'
                data = {'report':report,'details':details,'summary':summary,'synthetic':True,'persisted':False}
    finally:
        frappe.db.rollback()
        frappe.flags.analytics_local_validation = previous
        frappe.clear_cache()
        assert signature()==before, 'Preview modified existing source rows'
        frappe.db.rollback()
    target=EVIDENCE / 'visual-fixture.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data,ensure_ascii=False,indent=2))
    return {'synthetic':True,'persisted':False,'protected_rows_unchanged':True}
