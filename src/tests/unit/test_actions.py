import imp
import unittest.mock as mock

from pytest import mark


class TestActions():
    @mark.skip()
    def test_example_action(self, sysconfig, monkeypatch):
        mock_function = mock.Mock()
        monkeypatch.setattr(sysconfig, 'action_function', mock_function)
        assert mock_function.call_count == 0
        imp.load_source('action_function', './actions/example-action')
        assert mock_function.call_count == 1
