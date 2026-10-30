// Meta-test for GEMINI.md 3.5: a false check must fail the executable even in a
// Release build. CTest registers this target with WILL_FAIL. CTest does not
// invert a crash, so SIGABRT from the failed assertion is turned into exit
// code 1; if assertions were compiled out, main returns 0 and the test fails.
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <csignal>
#include <cstdlib>

extern "C" void on_abort(int) { std::_Exit(1); }

int main() {
    std::signal(SIGABRT, on_abort);
    volatile bool deliberately_false = false;
    assert(deliberately_false);
    return EXIT_SUCCESS;  // reached only if assertions were compiled out
}
