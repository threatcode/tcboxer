#!/usr/bin/python3

import os
import tempfile
import unittest

import kaboxer


class TestKaboxerApplication(unittest.TestCase):
    def setUp(self):
        self.obj = kaboxer.Kaboxer()

    def test_command_line_parser(self):
        subcommands = (
            ['build'],
            ['clean'],
            ['get-meta-file', 'app', 'file'],
            ['get-upstream-version', 'app'],
            ['install'],
            ['list'],
            ['load', 'app', 'file'],
            ['prepare', 'app'],
            ['purge', 'app'],
            ['push', 'app'],
            ['run', 'app'],
            ['save', 'app', 'file'],
            ['stop', 'app'],
            ['upgrade', 'app'],
        )
        for args in subcommands:
            with self.subTest('Parsing %s' % ' '.join(args)):
                self.obj.parser.parse_args(args=args)

    def test_generic_options(self):
        args = self.obj.parser.parse_args(args=['build'])
        self.assertEqual(args.verbose, 0)

        args = self.obj.parser.parse_args(args=['--verbose', 'build'])
        self.assertEqual(args.verbose, 1)

        args = self.obj.parser.parse_args(args=['-vv', 'build'])
        self.assertEqual(args.verbose, 2)


class TestKaboxerAppConfig(unittest.TestCase):

    def get_app_config(self, config=None):
        if config is None:
            config = self.sample_config
        return kaboxer.KaboxerAppConfig(config=config)

    def get_temp_app_config_file(self):
        f = tempfile.NamedTemporaryFile(prefix='kbx-tests-', suffix='.yml',
                                        delete=False)
        f.write(b'application:\n')
        f.write(b'  id: kbx-test\n')
        f.close()
        self.addCleanup(os.unlink, f.name)
        return f.name

    def setUp(self):
        self.sample_config = {
            'application': {
                'id': 'sample',
            }
        }
        self.obj = self.get_app_config(self.sample_config)

    def test_init_with_explicit_config(self):
        # init is done via setUp
        self.assertIsNone(self.obj.filename)

    def test_init_with_filename(self):
        filename = self.get_temp_app_config_file()
        self.obj = kaboxer.KaboxerAppConfig(filename=filename)

    def test_init_without_parameters(self):
        with self.assertRaises(ValueError):
            self.obj = kaboxer.KaboxerAppConfig()

    def test_special_method_getitem(self):
        # We want to be able to access the configuration directly
        # like a dict as that's how the legacy code expects it.
        self.assertEqual(self.obj['application']['id'], 'sample')

    def test_special_method_contains(self):
        # We want to be able to use "'foo' in obj" as the legacy
        # code uses it heavily.
        self.assertIn('application', self.obj)

    def test_app_id_attribute(self):
        self.assertEqual(self.obj.app_id, 'sample')

    def test_load_from_file(self):
        filename = self.get_temp_app_config_file()
        self.obj.load(filename)
        self.assertEqual(self.obj['application']['id'], 'kbx-test')
        self.assertEqual(self.obj.filename, filename)

    def test_save_to_file(self):
        # Get a unique filenanme that doesn't exist
        filename = self.get_temp_app_config_file()
        os.unlink(filename)
        # Change the id to something unique
        self.obj['application']['id'] = 'kbx-test-save'

        self.obj.save(filename)

        # Ensure we have the new configuration
        self.assertTrue(os.path.exists(filename))
        new = kaboxer.KaboxerAppConfig(filename=filename)
        self.assertEqual(new.app_id, 'kbx-test-save')


if __name__ == '__main__':
    unittest.main()
