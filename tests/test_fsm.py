import unittest

from instagram_story_parts.fsm import (
    InvalidStateTransition,
    SplitState,
    SplitStateMachine,
)


class SplitStateMachineTests(unittest.TestCase):
    def test_happy_path_records_each_transition(self):
        observed = []
        machine = SplitStateMachine(observed.append)

        expected = [
            SplitState.VALIDATING,
            SplitState.PROBING,
            SplitState.PLANNING,
            SplitState.EXPORTING,
            SplitState.COMPLETED,
        ]
        for state in expected:
            machine.transition_to(state)

        self.assertEqual(machine.state, SplitState.COMPLETED)
        self.assertEqual([event.current for event in machine.history], expected)
        self.assertEqual(observed, list(machine.history))

    def test_illegal_transition_does_not_mutate_state(self):
        machine = SplitStateMachine()

        with self.assertRaises(InvalidStateTransition):
            machine.transition_to(SplitState.EXPORTING)

        self.assertEqual(machine.state, SplitState.CREATED)
        self.assertEqual(machine.history, ())

    def test_fail_is_idempotent_for_terminal_state(self):
        machine = SplitStateMachine()
        machine.transition_to(SplitState.FAILED)

        self.assertIsNone(machine.fail())
        self.assertEqual(len(machine.history), 1)


if __name__ == "__main__":
    unittest.main()
