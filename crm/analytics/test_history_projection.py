"""The bounded report projection must preserve history semantics and numeric evidence."""
import json
import unittest
from copy import deepcopy

from crm.analytics.history import _project_deal_events, deal_history


class TestHistoryProjection(unittest.TestCase):
    def event(self, before, after, sequence=1, **payload):
        return {'name':f'event-{sequence}','source_name':'D1','event_kind':'Created' if sequence==1 else 'Updated',
                'history_complete':1,'occurred_at':'2026-10-26 12:00:00',
                'payload':{'before':before,'after':after,**payload}}

    def test_large_irrelevant_payload_is_not_retained_but_numeric_evidence_is(self):
        state={'status':'Open','deal_value':'100.00','expected_deal_value':'200.00','probability':'50','exchange_rate':'1',
               'unused_text':'CUSTOMER_TEXT_SENTINEL'+'x'*1000000}
        rows=[self.event(None,state)]
        original=deepcopy(rows)
        value=_project_deal_events({'D1':rows})['D1']
        self.assertEqual(value['fact'],deal_history(rows))
        self.assertEqual(value['latest_after'],{'deal_value':'100.00','expected_deal_value':'200.00','probability':'50','exchange_rate':'1'})
        self.assertNotIn('CUSTOMER_TEXT_SENTINEL',json.dumps(value))
        self.assertLess(len(json.dumps(value)),1500)
        self.assertEqual(rows,original)

    def test_loss_transition_forecast_push_and_absolute_time_survive(self):
        before={'status':'Open','expected_closure_date':'2026-10-30'}
        after={'status':'Lost','status_type':'Lost','expected_closure_date':'2026-11-05'}
        rows=[self.event(None,before),self.event(before,after,2,source_event={'occurred_at_utc':'2026-10-26T09:00:00Z'})]
        fact=_project_deal_events({'D1':rows})['D1']['fact']
        self.assertEqual(fact,deal_history(rows))
        self.assertEqual(fact['lost_date'],'2026-10-26T09:00:00Z')
        self.assertTrue(fact['close_date_pushed'])
        self.assertEqual(len(fact['transitions']),2)

    def test_owner_at_closure_survives_handoff_but_resets_on_reopening(self):
        active = {"status": "Open", "status_type": "Open", "deal_owner": "alex"}
        won = {**active, "status": "Won", "status_type": "Won", "closed_date": "2026-10-26"}
        reassigned = {**won, "deal_owner": "blair"}
        reopened = {**active, "deal_owner": "blair"}
        rows = [self.event(None, active), self.event(active, won, 2), self.event(won, reassigned, 3)]
        self.assertEqual(deal_history(rows)["outcome_attribution"]["owner"], "alex")
        rows.append(self.event(reassigned, reopened, 4))
        self.assertIsNone(deal_history(rows)["outcome_attribution"])
        won_again = {**won, "deal_owner": "blair"}
        rows.append(self.event(reopened, won_again, 5))
        self.assertEqual(deal_history(rows)["outcome_attribution"]["owner"], "blair")

    def test_missing_numbers_and_deleted_state_remain_unknown(self):
        row=self.event(None,{'status':'Open','deal_value':None,'probability':'0'})
        value=_project_deal_events({'D1':[row]})['D1']
        self.assertIsNone(value['latest_after']['deal_value'])
        self.assertEqual(value['latest_after']['probability'],'0')
        self.assertIsNone(value['latest_after']['exchange_rate'])
        deleted=self.event({'status':'Open'},None,2)
        self.assertIsNone(_project_deal_events({'D1':[row,deleted]})['D1']['latest_after'])
        self.assertIsNone(_project_deal_events({'D1':[]})['D1']['first'])
