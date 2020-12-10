#!/usr/bin/python3

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


if __name__ == '__main__':
    unittest.main()
