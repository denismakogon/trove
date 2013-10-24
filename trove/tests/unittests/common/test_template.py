#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at
#
#http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.


import testtools
import re
from yaml import load
from mock import Mock
from mockito import mock, when
from tempfile import NamedTemporaryFile
from trove.common import template
from trove.tests.unittests.util import util
from trove.common.exception import HeatTemplateNotFound

CONF = mock()


class TemplateTest(testtools.TestCase):
    def setUp(self):
        super(TemplateTest, self).setUp()
        util.init_db()
        self.env = template.ENV
        self.template = self.env.get_template("mysql.config.template")
        self.flavor_dict = {'ram': 1024}
        self.server_id = "180b5ed1-3e57-4459-b7a3-2aeee4ac012a"
        self.orig_conf = template.CONF
        when(CONF).get('service_type').thenReturn('mysql')

    def tearDown(self):
        super(TemplateTest, self).tearDown()
        template.CONF = self.orig_conf

    def validate_template(self, contents, teststr, test_flavor, server_id):
        # expected query_cache_size = {{ 8 * flavor_multiplier }}M
        flavor_multiplier = test_flavor['ram'] / 512
        found_group = None
        for line in contents.split('\n'):
            m = re.search('^%s.*' % teststr, line)
            if m:
                found_group = m.group(0)
        if not found_group:
            raise "Could not find text in template"
        # Check that the last group has been rendered
        memsize = found_group.split(" ")[2]
        self.assertEqual(memsize, "%sM" % (8 * flavor_multiplier))
        self.assertIsNotNone(server_id)
        self.assertTrue(server_id > 1)

    def test_rendering(self):
        rendered = self.template.render(flavor=self.flavor_dict,
                                        server_id=self.server_id)
        self.validate_template(rendered,
                               "query_cache_size",
                               self.flavor_dict,
                               self.server_id)

    def test_single_instance_config_rendering(self):
        config = template.SingleInstanceConfigTemplate('mysql',
                                                       self.flavor_dict,
                                                       self.server_id)
        self.validate_template(config.render(), "query_cache_size",
                               self.flavor_dict, self.server_id)

    def test_heat_template_loading_exception(self):
        """ tests the loading of heat templates from base dir"""
        # 1. test for Exception when the template is not found
        self.assertRaises(HeatTemplateNotFound,
                          template.HeatTemplate.get_template)

    def test_heat_template_loading_and_validating(self):

        # 2.test validity of the loaded template
        # this test comes from Denis M's valued code suggestions
        with NamedTemporaryFile(mode="w",
                                suffix=".heat.template",
                                delete=False) as tmp_file:
            tmp_file.write(str({'BaseInstance': dict()}))
        template.HeatTemplate.read_template = Mock(
            return_value=open(tmp_file.name).read())
        when(CONF).get('service_type').thenReturn(tmp_file.name)
        self.assertNotEqual(None,
                            template.HeatTemplate.
                            get_template(CONF.service_type))
