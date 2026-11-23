import base64
import json
import unittest
from preflight.amendment001 import valid_history

class OverloadAmendmentChecks(unittest.TestCase):
    def test_only_explicit_jev_overload_is_added(self):
        def row(kind):return {'status':529,'response_body_b64':base64.b64encode(json.dumps({'detail':{'error_type':kind}}).encode()).decode()}
        valid_history([row('system_overloaded'),{'status':429}],'typesafe')
        with self.assertRaises(ValueError):valid_history([row('other_error')],'typesafe')
        with self.assertRaises(ValueError):valid_history([row('system_overloaded')],'together')
        with self.assertRaises(ValueError):valid_history([{'status':401}],'typesafe')
        with self.assertRaises(ValueError):valid_history([{'status':529,'response_body_b64':'!'}],'typesafe')

if __name__=='__main__':unittest.main()
