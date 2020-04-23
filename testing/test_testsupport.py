def test_spec(test_plugin_manager, add_specification):
    assert not test_plugin_manager.hook.items()
    assert not hasattr(test_plugin_manager.hook, 'my_spec')

    @add_specification
    def my_spec(arg1, arg2):
        ...

    assert hasattr(test_plugin_manager.hook, 'my_spec')
    assert hasattr(test_plugin_manager.hook.my_spec, 'spec')


def test_full(test_plugin_manager, add_specification, add_implementation):
    relay = test_plugin_manager.hook
    assert not relay.items()

    @add_specification
    def my_spec(arg1, arg2):
        ...

    assert hasattr(relay, 'my_spec')
    assert not relay.my_spec.get_hookimpls()

    @add_implementation(specname='my_spec')
    def ttt(arg):
        return arg + 1

    assert relay.my_spec.get_hookimpls()[0].specname == 'my_spec'


def test_caller_from_implementation(caller_from_implementation):
    def test1(arg):
        return arg + 1

    caller = caller_from_implementation(test1)
    assert caller.get_hookimpls()[0].function == test1
    assert caller(arg=1) == [2]

    def test2(arg):
        return arg + 1

    caller = caller_from_implementation(test2, {'firstresult': True})
    assert caller.get_hookimpls()[0].function == test2
    assert caller(arg=1) == 2
