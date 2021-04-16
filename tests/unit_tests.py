#!/usr/bin/python3

import json
import os
import responses
import shutil
import tempfile
import unittest

from kaboxer import ContainerRegistry, DockerBackend, Kaboxer, KaboxerAppConfig
from kaboxer import get_possible_gitlab_project_paths


class TestKaboxerApplication(unittest.TestCase):
    def setUp(self):
        self.obj = Kaboxer()

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


class TestKaboxerFindConfigsInDir(unittest.TestCase):
    def setUp(self):
        self.obj = Kaboxer()
        # annoying logger
        import logging
        self.obj.logger = logging.Logger('kaboxer')
        self.configs_dir = tempfile.mkdtemp()
        self.mk_config_file('foo')
        self.mk_config_file('bar')
        self.mk_config_file('bar', filename='kaboxer.yaml')

    def tearDown(self):
        shutil.rmtree(self.configs_dir)

    def mk_config_file(self, app_id, filename=None):
        if not filename:
            filename = app_id + '.kaboxer.yaml'
        config_data = {
            'application': {
                'id': app_id,
            }
        }
        config = KaboxerAppConfig(config=config_data)
        config.save(os.path.join(self.configs_dir, filename))

    def assertConfigsAppIds(self, app_configs, app_ids):
        configs_app_ids = [c.app_id for c in app_configs]
        self.assertEqual(sorted(configs_app_ids), sorted(app_ids))

    def test_restrict_none_duplicate_true(self):
        configs = self.obj.find_configs_in_dir(self.configs_dir,
                restrict=None, allow_duplicate=True)
        self.assertConfigsAppIds(configs, ['foo', 'bar', 'bar'])

    def test_restrict_none_duplicate_false(self):
        configs = self.obj.find_configs_in_dir(self.configs_dir,
                restrict=None, allow_duplicate=False)
        self.assertConfigsAppIds(configs, ['foo', 'bar'])

    def test_restrict_set_duplicate_true(self):
        configs = self.obj.find_configs_in_dir(self.configs_dir,
                restrict=['bar'], allow_duplicate=True)
        self.assertConfigsAppIds(configs, ['bar', 'bar'])

    def test_restrict_set_duplicate_false(self):
        configs = self.obj.find_configs_in_dir(self.configs_dir,
                restrict=['bar'], allow_duplicate=False)
        self.assertConfigsAppIds(configs, ['bar'])


class TestKaboxerAppConfig(unittest.TestCase):

    def get_app_config(self, config=None):
        if config is None:
            config = self.sample_config
        return KaboxerAppConfig(config=config)

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
        self.obj = KaboxerAppConfig(filename=filename)

    def test_init_without_parameters(self):
        with self.assertRaises(ValueError):
            self.obj = KaboxerAppConfig()

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

    def test_get_existing_key(self):
        self.assertEqual(self.obj.get('application:id'), 'sample')

    def test_get_non_existing_key(self):
        self.assertIsNone(self.obj.get('application:bad:key'))

    def test_get_non_existing_key_default_value(self):
        self.assertEqual(self.obj.get('application:bad:key', 'default'),
                         'default')

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
        new = KaboxerAppConfig(filename=filename)
        self.assertEqual(new.app_id, 'kbx-test-save')


class TestDockerBackend(unittest.TestCase):
    def setUp(self):
        self.obj = DockerBackend()
        self.config = {
            'application': {
                'id': 'kbx-docker-test'
            },
            'container': {
                'type': 'docker',
                'origin': {},
            }
        }
        self.app_config = KaboxerAppConfig(config=self.config)

    def set_origin_registry(self, url, image=None):
        data = {'url': url}
        if image:
            data['image'] = image
        self.config['container']['origin']['registry'] = data

    def test_get_local_image_name(self):
        self.assertEqual(self.obj.get_local_image_name(self.app_config),
                         'kaboxer/kbx-docker-test')

    def test_get_remote_image_name_no_registry_data(self):
        self.set_origin_registry(None)
        self.assertIsNone(self.obj.get_remote_image_name(self.app_config))

    def test_get_remote_image_name_invalid_registry_data(self):
        self.assertIsNone(self.obj.get_remote_image_name(self.app_config))

    def test_get_remote_image_name_with_default_image_name(self):
        self.set_origin_registry('https://foo.bar.com/registry')
        self.assertEqual(self.obj.get_remote_image_name(self.app_config),
                         'foo.bar.com/registry/kbx-docker-test')

    def test_get_remote_image_name_with_explicit_image_name(self):
        self.set_origin_registry('https://foo.bar.com/registry', 'myname')
        self.assertEqual(self.obj.get_remote_image_name(self.app_config),
                         'foo.bar.com/registry/myname')


class TestContainerRegistry(unittest.TestCase):

    NOT_FOUND = None

    def setUp(self):
        self.obj = ContainerRegistry()
        self.json_fixture_dir = 'tests/fixtures/'
        self.api_url = 'not-set-yet'
        self.url_templates = {}

    def get_url(self, key, **kwargs):
        template = self.url_templates[key]
        formatted = template.format(**kwargs)
        return self.api_url + formatted

    def set_url_response_as_json_fixture(self, url, json_file):
        json_path = os.path.join(self.json_fixture_dir, json_file)
        with open(json_path) as f:
            json_data = json.load(f)
        responses.add(responses.GET, url, json=json_data, status=200)

    def set_url_response_not_found(self, url):
        responses.add(responses.GET, url, body='{}', status=404)


class TestDockerContainerRegistry(TestContainerRegistry):
    def setUp(self):
        super().setUp()
        self.json_fixture_dir += 'not-implemented'
        self.api_url = 'not-implemented'
        self.url_templates = {}

    @unittest.skip("Not implemented yet")
    def test_get_image(self):
        pass


class TestDockerHubContainerRegistry(TestContainerRegistry):
    def setUp(self):
        super().setUp()
        self.json_fixture_dir += 'docker-hub-registry-v2'
        self.api_url = 'https://registry.hub.docker.com/v2'
        self.url_templates = {
            'tags': '/repositories/{image}/tags'
        }

    def setup_responses_for_tags(self, image, json_file):
        url = self.get_url('tags', image=image)
        if json_file:
            self.set_url_response_as_json_fixture(url, json_file)
        else:
            self.set_url_response_not_found(url)

    @responses.activate
    def test_get_non_existing_image(self):
        self.setup_responses_for_tags('foo/bar', self.NOT_FOUND)
        tags = self.obj._get_tags_docker_hub_registry('foo/bar')
        self.assertEqual(tags, [])

    @responses.activate
    def test_get_image(self):
        self.setup_responses_for_tags('foo/bar', 'tags.json')
        tags = self.obj._get_tags_docker_hub_registry('foo/bar')
        self.assertEqual(tags, [ 'latest', '0.5' ])


class TestGitlabContainerRegistry(TestContainerRegistry):
    def setUp(self):
        super().setUp()
        self.json_fixture_dir += 'gitlab-registry-v4'
        self.api_url = 'https://gitlab.com/api/v4'
        self.url_templates = {
            'repos': '/projects/{proj}/registry/repositories',
            'tags' : '/projects/{proj_id}/registry/repositories/{repo_id}/tags',
        }

    def _setup_responses_for_repos(self, project, json_file):
        """
        Setup response for the first request, ie. the request to get
        the list of repositories in a project.
        https://docs.gitlab.com/ce/api/container_registry.html#within-a-project
        """
        project_url_encoded = project.replace('/', '%2F')
        url = self.get_url('repos', proj=project_url_encoded)
        if json_file:
            self.set_url_response_as_json_fixture(url, json_file)
        else:
            self.set_url_response_not_found(url)

    def _setup_responses_for_tags(self, project_id, repository_id, json_file):
        """
        Setup response for the second request, ie. the request to get
        the list of tags for a given repository.
        https://docs.gitlab.com/ce/api/container_registry.html#within-a-project-1
        """
        url = self.get_url('tags', proj_id=project_id, repo_id=repository_id)
        if json_file:
            self.set_url_response_as_json_fixture(url, json_file)
        else:
            self.set_url_response_not_found(url)

    def _setup_not_found_responses(self, project, image):
        """
        Setup 404 not found responses for various urls. These are all the
        paths from <project>/elem1 until <project>/elem1/.../elemN, with elems
        being parts of image. All these paths are NOT project paths.
        """
        if not image:
            return

        path = project
        for elem in image.split('/'):
            path = path + '/' + elem
            url_encoded = path.replace('/', '%2F')
            url = self.get_url('repos', proj=url_encoded)
            self.set_url_response_not_found(url)

    def setup_responses(self, project, image, repos_json, proj_id, repo_id, tags_json):
        """
        Setup responses for a test. Short how to:
        - if 'project' is supposed to exist, then provide 'repos_json' (the list of
          repos in this project).
        - 'image' can be an empty string, this is valid.
        - if 'image' is supposed to be found in this project, then provide 'proj_id'
          and 'repo_id'. Look for their values in the repos_json file. Additionally,
          you should provide 'tags_json' (the list of tags for this image), unless
          you want to simulate some kind of unexpected 'not found' error.
        """
        # set response for the 1st http request
        self._setup_responses_for_repos(project, repos_json)

        # set response for the 2nd http request
        if proj_id > 0 and repo_id > 0:
            self._setup_responses_for_tags(proj_id, repo_id, tags_json)

        # set all the 'not found' responses for the requests that we expect
        # to be sent (this is because responses prints some warnings when a
        # request does not have a match, and we don't want that)
        self._setup_not_found_responses(project, image)

    @responses.activate
    def test_get_image_invalid_project_no_image_name(self):
        self.setup_responses('too-short', '', self.NOT_FOUND, -1, -1, self.NOT_FOUND)
        tags = self.obj._get_tags_gitlab_registry('too-short')
        self.assertEqual(tags, [])

    def test_get_image_invalid_project_with_image_name(self):
        self.setup_responses('too-short', 'image', self.NOT_FOUND, -1, -1, self.NOT_FOUND)
        tags = self.obj._get_tags_gitlab_registry('too-short/image')
        self.assertEqual(tags, [])

    @responses.activate
    def test_get_image_non_existing_project(self):
        self.setup_responses('foo/bar', '', self.NOT_FOUND, -1, -1, self.NOT_FOUND)
        tags = self.obj._get_tags_gitlab_registry('foo/bar')
        self.assertEqual(tags, [])

    @responses.activate
    def test_get_image_depth_level_1(self):
        self.setup_responses('group/project', '', 'project-repositories.json',
                9, 1, 'project-tags.json')
        tags = self.obj._get_tags_gitlab_registry('group/project')
        self.assertEqual(tags, [ 'A', 'latest' ])

    @responses.activate
    def test_get_image_depth_level_2(self):
        self.setup_responses('group/project', 'foo', 'project-repositories.json',
                9, 2, 'project-foo-tags.json')
        tags = self.obj._get_tags_gitlab_registry('group/project/foo')
        self.assertEqual(tags, [ 'B' ])

    @responses.activate
    def test_get_image_depth_level_3(self):
        self.setup_responses('group/project', 'foo/bar', 'project-repositories.json',
                9, 3, 'project-foo-bar-tags.json')
        tags = self.obj._get_tags_gitlab_registry('group/project/foo/bar')
        self.assertEqual(tags, [ 'C' ])

    @responses.activate
    def test_get_image_non_existing_image_1(self):
        self.setup_responses('group/project', 'no-such-image',
                'project-repositories.json', -1, -1, self.NOT_FOUND)
        tags = self.obj._get_tags_gitlab_registry('group/project/no-such-image')
        self.assertEqual(tags, [])

    @responses.activate
    def test_get_image_non_existing_image_2(self):
        self.setup_responses('group/project', 'foo',
                'project-repositories.json', 9, 2, self.NOT_FOUND)
        tags = self.obj._get_tags_gitlab_registry('group/project/foo')
        self.assertEqual(tags, [])


class TestGetPossibleGitlabProjectPaths(unittest.TestCase):
    def test_get_possible_gitlab_project_paths(self):
        path = 'group/project'
        pp = get_possible_gitlab_project_paths(path)
        self.assertEqual(pp, [ 'group/project' ])

        path = 'group/project/foo'
        pp = get_possible_gitlab_project_paths(path)
        self.assertEqual(pp, [ 'group/project', 'group/project/foo' ])

        path = 'group/project/foo/bar'
        pp = get_possible_gitlab_project_paths(path)
        self.assertEqual(pp, [ 'group/project/foo',
            'group/project/foo/bar', 'group/project' ])


if __name__ == '__main__':
    unittest.main()
