"""Protect sizing measurements from counter/format interpretation errors."""
import copy
import importlib.util
from pathlib import Path
import unittest


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


observer = module('capacity_observer', 'manual/observe_capacity.py')
chat = module('capacity_chat', 'measure_public_chat.py')
host = module('capacity_host', 'manual/check_application_host.py')


class CapacityToolsTest(unittest.TestCase):
    def pair(self):
        container = {'generation': 'same', 'running': True, 'healthy': True,
                     'oom_killed': False, 'restarts': 0, 'memory_bytes': 100,
                     'lifetime_memory_peak_bytes': 200, 'memory_limit_bytes': 1000,
                     'cpu_usage_usec': 0, 'memory_limit_events': 0,
                     'oom_events': 0, 'oom_kill_events': 0}
        first = {'at': 'start', 'monotonic': 10, 'host_cpu_total': 1000, 'host_cpu_idle': 900,
                 'host_memory_total_bytes': 2 * 1024**3,
                 'host_memory_available_bytes': 512 * 1024**2,
                 'host_swap_total_bytes': 0, 'host_swap_free_bytes': 0,
                 'root_free_bytes': 5 * 1024**3, 'data_free_bytes': 10 * 1024**3,
                 'containers': {'backend': copy.deepcopy(container), 'proxy': copy.deepcopy(container)}}
        last = copy.deepcopy(first)
        last.update(at='end', monotonic=20, host_cpu_total=3000, host_cpu_idle=1900)
        last['containers']['backend']['cpu_usage_usec'] = 10_000_000
        return first, last

    def test_cpu_is_normalized_by_two_vcpus_and_sampling_does_not_replace_lifetime_peak(self):
        report = observer.summarize(self.pair())
        self.assertEqual(report['containers']['backend']['average_cpu_percent_of_two_vcpus'], 50)
        self.assertEqual(report['sample_interval_cpu_peak_percent'], 50)
        self.assertEqual(report['containers']['backend']['sampled_memory_peak_bytes'], 100)
        self.assertEqual(report['containers']['backend']['lifetime_memory_peak_after_bytes'], 200)
        self.assertTrue(report['load_guard_ok'])

    def test_replacement_invalidates_even_an_apparently_healthy_container(self):
        first, last = self.pair()
        last['containers']['backend']['generation'] = 'replaced'
        self.assertFalse(observer.summarize([first, last])['load_guard_ok'])

    def test_memory_pressure_and_new_oom_block_an_increase_in_load(self):
        for issue in ('pressure', 'oom', 'oom_kill'):
            with self.subTest(issue=issue):
                first, last = self.pair()
                if issue == 'pressure':
                    last['host_memory_available_bytes'] = 128 * 1024**2
                elif issue == 'oom':
                    last['containers']['backend']['oom_events'] = 1
                else:
                    last['containers']['backend']['oom_kill_events'] = 1
                self.assertFalse(observer.summarize([first, last])['load_guard_ok'])

    def test_response_code_handles_typography_without_accepting_a_different_identifier(self):
        self.assertTrue(chat.marker_found('**CAPACITY\u201120261019**', 'CAPACITY-20261019'))
        self.assertFalse(chat.marker_found('CAPACITY-20261020', 'CAPACITY-20261019'))

    def test_operational_log_export_omits_user_content_and_unrecognized_counts(self):
        output = host.public_event({'event': 'rag.retrieval', 'status': 'success',
            'question': 'private synthetic text', 'tenant_id': 'private-id',
            'counts': {'returned_results': 2, 'question': 'private synthetic text', 'vector_candidates': -1}})
        self.assertEqual(output, {'event': 'rag.retrieval', 'status': 'success', 'counts': {'returned_results': 2}})
        self.assertIsNone(host.public_event({'event': 'unknown', 'message': 'private synthetic text'}))


if __name__ == '__main__':
    unittest.main()
