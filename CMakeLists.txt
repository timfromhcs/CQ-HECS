cmake_minimum_required(VERSION 3.24)
project(CQ_HECS VERSION 7.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Build artifacts stay inside the binary directory. Writing them into the
# source tree made `git status` noisy, broke out-of-source builds and meant a
# stale binary from a previous checkout could be picked up by tests.
set(CQ_OUTPUT_ROOT "${CMAKE_BINARY_DIR}/bin")
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CQ_OUTPUT_ROOT}")
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CQ_OUTPUT_ROOT}/Release")
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CQ_OUTPUT_ROOT}")
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_RELEASE "${CQ_OUTPUT_ROOT}/Release")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${CQ_OUTPUT_ROOT}")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_RELEASE "${CQ_OUTPUT_ROOT}/Release")

if(MSVC)
    add_compile_options(/W4 /permissive- /Zc:preprocessor)
    # P-06 reproducible Windows binaries: /Brepro replaces the PE/COFF link
    # timestamp (and the debug-directory/object timestamps) with a content hash;
    # /PDBALTPATH strips the build-directory path from the embedded PDB path.
    # Verified by building twice and comparing SHA-256 (docs/PACKAGING.md).
    # Release only: Debug/incremental builds are not a reproducibility target.
    add_compile_options("$<$<CONFIG:Release,RelWithDebInfo,MinSizeRel>:/Brepro>")
    add_link_options("$<$<CONFIG:Release,RelWithDebInfo,MinSizeRel>:/Brepro>"
                     "$<$<CONFIG:Release,RelWithDebInfo,MinSizeRel>:/PDBALTPATH:%_PDB%>")
else()
    add_compile_options(-Wall -Wextra)
endif()

# Portable baseline by default. AVX2 is opt-in and applied per target so that
# enabling it cannot silently make unrelated binaries crash on older CPUs.
option(CQ_ENABLE_AVX2 "Enable AVX2 SIMD optimizations" OFF)
if(CQ_ENABLE_AVX2)
    message(STATUS "CQ_ENABLE_AVX2=ON: AVX2 will be enabled on selected targets only")
    if(MSVC)
        set(CQ_AVX2_FLAGS /arch:AVX2)
    else()
        set(CQ_AVX2_FLAGS -mavx2)
    endif()
else()
    set(CQ_AVX2_FLAGS "")
endif()

if(WIN32)
    if(NOT DEFINED ENV{VULKAN_SDK} OR NOT EXISTS "$ENV{VULKAN_SDK}")
        file(GLOB _VULKAN_CANDIDATE_DIRS "C:/VulkanSDK/*")
        if(_VULKAN_CANDIDATE_DIRS)
            list(SORT _VULKAN_CANDIDATE_DIRS ORDER DESCENDING)
            list(GET _VULKAN_CANDIDATE_DIRS 0 _LATEST_VULKAN_DIR)
            set(ENV{VULKAN_SDK} "${_LATEST_VULKAN_DIR}")
            message(STATUS "Auto-detected Vulkan SDK at: ${_LATEST_VULKAN_DIR}")
        endif()
    endif()

    if(DEFINED ENV{VULKAN_SDK} AND EXISTS "$ENV{VULKAN_SDK}")
        list(APPEND CMAKE_PREFIX_PATH "$ENV{VULKAN_SDK}")
        if(EXISTS "$ENV{VULKAN_SDK}/Include/vulkan/vulkan.h")
            set(Vulkan_INCLUDE_DIR "$ENV{VULKAN_SDK}/Include" CACHE PATH "Vulkan include directory" FORCE)
        else()
            file(GLOB_RECURSE _FOUND_VULKAN_H "$ENV{VULKAN_SDK}/*/vulkan.h" "$ENV{VULKAN_SDK}/vulkan.h")
            if(_FOUND_VULKAN_H)
                list(GET _FOUND_VULKAN_H 0 _VULKAN_H_PATH)
                get_filename_component(_VULKAN_DIR ${_VULKAN_H_PATH} DIRECTORY)
                get_filename_component(_VULKAN_INC ${_VULKAN_DIR} DIRECTORY)
                set(Vulkan_INCLUDE_DIR "${_VULKAN_INC}" CACHE PATH "Vulkan include directory" FORCE)
                message(STATUS "Found Vulkan header at ${_VULKAN_H_PATH}, setting Vulkan_INCLUDE_DIR=${_VULKAN_INC}")
            endif()
        endif()

        if(EXISTS "$ENV{VULKAN_SDK}/Lib/vulkan-1.lib")
            set(Vulkan_LIBRARY "$ENV{VULKAN_SDK}/Lib/vulkan-1.lib" CACHE FILEPATH "Vulkan library" FORCE)
            message(STATUS "Setting Vulkan_LIBRARY=$ENV{VULKAN_SDK}/Lib/vulkan-1.lib")
        elseif(EXISTS "$ENV{VULKAN_SDK}/Lib/vulkan.lib")
            set(Vulkan_LIBRARY "$ENV{VULKAN_SDK}/Lib/vulkan.lib" CACHE FILEPATH "Vulkan library" FORCE)
            message(STATUS "Setting Vulkan_LIBRARY=$ENV{VULKAN_SDK}/Lib/vulkan.lib")
        else()
            file(GLOB_RECURSE _FOUND_VULKAN_LIB "$ENV{VULKAN_SDK}/*vulkan-1.lib" "$ENV{VULKAN_SDK}/*vulkan.lib")
            foreach(_CANDIDATE ${_FOUND_VULKAN_LIB})
                if(NOT _CANDIDATE MATCHES "ARM" AND NOT _CANDIDATE MATCHES "Lib32")
                    set(Vulkan_LIBRARY "${_CANDIDATE}" CACHE FILEPATH "Vulkan library" FORCE)
                    message(STATUS "Found Vulkan library at ${_CANDIDATE}, setting Vulkan_LIBRARY=${_CANDIDATE}")
                    break()
                endif()
            endforeach()
        endif()
    endif()
endif()

# Two native configurations (AGENTS_V6.md W3 / T6-03):
#   -DCQ_ENABLE_VULKAN=ON  (default) full build; requires the Vulkan SDK.
#   -DCQ_ENABLE_VULKAN=OFF CPU-only: the CPU-pure targets (cq_hecs_core C-ABI
#     library, stabilizer/MPS/statevector/exact-ring/SAT-parser tests). The CLI,
#     the cq_hecs C-ABI facade, VRTS300/ConstraintSolver, examples and the Vulkan
#     tests are excluded, and no binary links the Vulkan loader
#     (tests/test_native_cpu_only.py). The Python package never needs Vulkan.
option(CQ_ENABLE_VULKAN "Build the Vulkan compute integration (requires the Vulkan SDK); OFF = CPU-only build" ON)
option(CQ_ENABLE_SANITIZERS "Enable Address and UB sanitizers (GNU/Clang)" OFF)

if(CQ_ENABLE_SANITIZERS)
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        message(STATUS "CQ_ENABLE_SANITIZERS=ON: address,undefined for all native targets")
        add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
        add_link_options(-fsanitize=address,undefined)
    elseif(MSVC)
        # MSVC ships AddressSanitizer only (no UBSan). Use a Release/RelWithDebInfo
        # configuration: /fsanitize=address is incompatible with /RTC1 (Debug) and
        # with incremental linking. The runtime DLL
        # (clang_rt.asan_dynamic-x86_64.dll) must be on PATH when running tests.
        message(STATUS "CQ_ENABLE_SANITIZERS=ON: MSVC AddressSanitizer only (no UBSan)")
        add_compile_options(/fsanitize=address)
        add_link_options(/INCREMENTAL:NO)
    else()
        message(FATAL_ERROR
            "CQ_ENABLE_SANITIZERS requires GCC, Clang or MSVC; "
            "${CMAKE_CXX_COMPILER_ID} does not support these flags.")
    endif()
endif()

set(CQ_HAVE_VULKAN OFF)
if(CQ_ENABLE_VULKAN)
    find_package(Vulkan REQUIRED)
    set(CQ_HAVE_VULKAN ON)
    message(STATUS "Vulkan: ${Vulkan_LIBRARY} (version ${Vulkan_VERSION})")
else()
    # CPU-only build (T6-03). Everything that includes <vulkan/vulkan.h> -- the
    # CLI, the C-ABI facade, the VRTS300/ConstraintSolver engines, the examples
    # and the Vulkan tests -- is EXCLUDED rather than stubbed, so a CPU binary
    # can never claim a GPU path. Only the CPU-pure targets below are built and
    # none of them links the Vulkan loader.
    message(STATUS "CQ_ENABLE_VULKAN=OFF: CPU-only native build (Vulkan targets excluded)")
endif()

# -----------------------------------------------------------------------------
# Automated Vulkan 1.3 SPIR-V Shader Compilation Target (glslangValidator)
# -----------------------------------------------------------------------------
if(CQ_HAVE_VULKAN)
    find_program(GLSLANG_VALIDATOR glslangValidator HINTS "$ENV{VULKAN_SDK}/bin" "$ENV{VULKAN_SDK}/Bin")
endif()
if(CQ_HAVE_VULKAN AND GLSLANG_VALIDATOR)
    message(STATUS "Found glslangValidator for automated SPIR-V compilation: ${GLSLANG_VALIDATOR}")
    file(GLOB_RECURSE SHADER_COMP_FILES "${CMAKE_SOURCE_DIR}/shaders/*.comp")
    set(SPIRV_BINARY_FILES "")
    foreach(SHADER_SRC ${SHADER_COMP_FILES})
        get_filename_component(SHADER_NAME ${SHADER_SRC} NAME_WE)
        get_filename_component(SHADER_DIR ${SHADER_SRC} DIRECTORY)
        set(SPV_OUT "${SHADER_DIR}/${SHADER_NAME}.spv")
        add_custom_command(
            OUTPUT ${SPV_OUT}
            COMMAND ${GLSLANG_VALIDATOR} --target-env vulkan1.3 -V ${SHADER_SRC} -o ${SPV_OUT}
            DEPENDS ${SHADER_SRC}
            COMMENT "Compiling Vulkan 1.3 SPIR-V shader: ${SHADER_NAME}.comp -> ${SHADER_NAME}.spv"
            VERBATIM
        )
        list(APPEND SPIRV_BINARY_FILES ${SPV_OUT})
    endforeach()
    add_custom_target(vulkan_shaders ALL DEPENDS ${SPIRV_BINARY_FILES})
elseif(CQ_HAVE_VULKAN)
    message(WARNING "glslangValidator not found. Using pre-compiled SPIR-V shaders.")
endif()

include_directories(
    include
    src
    ${Vulkan_INCLUDE_DIRS}
)

# CPU-pure objects shared by the CPU-only and the Vulkan builds.
add_library(cq_hecs_cpu_objects OBJECT src/sat_solver.cpp src/sat_solver.hpp)
set_target_properties(cq_hecs_cpu_objects PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_include_directories(cq_hecs_cpu_objects PRIVATE include src)

if(CQ_HAVE_VULKAN)
set(VRTS_SOURCES
    src/lattice.cpp
    src/cordic_engine.cpp
    src/residual_engine.cpp
    src/tensor_network.cpp
    src/constraint_solver.cpp
    src/vulkan/vulkan_context.cpp
    src/vulkan/vulkan_buffer.cpp
    src/vulkan/vulkan_pipeline.cpp
)

set(VRTS_HEADERS
    include/cq_hecs/lattice.hpp
    include/cq_hecs/cordic_engine.hpp
    include/cq_hecs/residual_engine.hpp
    include/cq_hecs/tensor_network.hpp
    include/cq_hecs/constraint_solver.hpp
    include/cq_hecs/vulkan/vulkan_context.hpp
    include/cq_hecs/vulkan/vulkan_buffer.hpp
    include/cq_hecs/vulkan/vulkan_pipeline.hpp
    include/cq_hecs/vulkan/vulkan_memory.hpp
    src/vulkan/shaders_vrts_embedded.hpp
)

set(CORE_SOURCES
    src/vulkan_engine.cpp
    src/entropy_harvester.cpp
    src/tiered_storage.cpp
    src/qasm_parser.cpp
    src/sat_solver.cpp
    src/arx_engine.cpp
    src/terminal_ui.cpp
    src/json_formatter.cpp
    ${VRTS_SOURCES}
)

set(CORE_HEADERS
    include/cq_hecs_api.h
    src/vulkan_engine.hpp
    src/entropy_harvester.hpp
    src/tiered_storage.hpp
    src/qasm_parser.hpp
    src/sat_solver.hpp
    src/arx_engine.hpp
    src/terminal_ui.hpp
    src/json_formatter.hpp
    src/shaders_embedded.hpp
    ${VRTS_HEADERS}
)

# The core is compiled exactly once into an object library and reused by every
# target. Previously each of ~14 targets recompiled the same files, which made
# builds slow and risked inconsistent binaries between targets.
add_library(cq_hecs_core_objects OBJECT ${CORE_SOURCES} ${CORE_HEADERS})
set_target_properties(cq_hecs_core_objects PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_include_directories(cq_hecs_core_objects PRIVATE ${Vulkan_INCLUDE_DIRS})
target_link_libraries(cq_hecs_core_objects PRIVATE ${Vulkan_LIBRARIES})
target_compile_definitions(cq_hecs_core_objects PUBLIC CQ_HECS_VERSION="${PROJECT_VERSION}")

# AVX2 is opt-in and target-scoped: it is applied only to this core object
# library, and only when explicitly requested. It is never set globally, so
# enabling it cannot make unrelated binaries require AVX2 hardware.
if(CQ_AVX2_FLAGS)
    target_compile_options(cq_hecs_core_objects PRIVATE ${CQ_AVX2_FLAGS})
endif()
if(TARGET vulkan_shaders)
    add_dependencies(cq_hecs_core_objects vulkan_shaders)
endif()

# 1. Standalone Monolithic Executable (CLI)
add_executable(cq_hecs src/main.cpp $<TARGET_OBJECTS:cq_hecs_core_objects>)
target_link_libraries(cq_hecs PRIVATE ${Vulkan_LIBRARIES})
target_compile_definitions(cq_hecs PRIVATE CQ_HECS_VERSION="${PROJECT_VERSION}")

# 2. C-ABI Shared Library (cq_hecs.dll / libcq_hecs.so)
add_library(cq_hecs_shared SHARED src/cq_hecs_api.cpp $<TARGET_OBJECTS:cq_hecs_core_objects>)
set_target_properties(cq_hecs_shared PROPERTIES
    OUTPUT_NAME "cq_hecs"
    DEFINE_SYMBOL "CQ_HECS_EXPORTS"
)
target_link_libraries(cq_hecs_shared PRIVATE ${Vulkan_LIBRARIES})
if(TARGET vulkan_shaders)
    add_dependencies(cq_hecs_shared vulkan_shaders)
endif()

# 3. Deterministic Test Executables
add_executable(test_reversibility tests/test_reversibility.cpp $<TARGET_OBJECTS:cq_hecs_core_objects>)
target_link_libraries(test_reversibility PRIVATE ${Vulkan_LIBRARIES})

add_executable(test_ghz300 tests/test_ghz300.cpp $<TARGET_OBJECTS:cq_hecs_core_objects>)
target_link_libraries(test_ghz300 PRIVATE ${Vulkan_LIBRARIES})

add_executable(test_constraint_solver tests/test_constraint_solver.cpp $<TARGET_OBJECTS:cq_hecs_core_objects>)
target_link_libraries(test_constraint_solver PRIVATE ${Vulkan_LIBRARIES})

add_executable(test_engine_cpp tests/test_engine_cpp.cpp $<TARGET_OBJECTS:cq_hecs_core_objects>)
target_link_libraries(test_engine_cpp PRIVATE ${Vulkan_LIBRARIES})

# 4. Examples
add_executable(ghz300_example examples/ghz300_example.cpp $<TARGET_OBJECTS:cq_hecs_core_objects>)
target_link_libraries(ghz300_example PRIVATE ${Vulkan_LIBRARIES})

add_executable(maxcut_example examples/maxcut_example.cpp $<TARGET_OBJECTS:cq_hecs_core_objects>)
target_link_libraries(maxcut_example PRIVATE ${Vulkan_LIBRARIES})

endif()  # CQ_HAVE_VULKAN: Vulkan-dependent core, CLI, C-ABI facade and examples

option(CQ_BUILD_TESTS "Build test suite" ON)
option(CQHECS_BUILD_TESTS "Build test suite" ON)
option(CQHECS_HEADLESS "Enable Headless SwiftShader / Software Vulkan ICD" OFF)

if(CQHECS_HEADLESS)
    add_compile_definitions(CQHECS_HEADLESS=1)
endif()

# 5. Shared Library: cq_hecs_core (C-API & Core Engine)
add_library(cq_hecs_core SHARED
    src/cq_c_api.cpp
    src/hybrid_engine.cpp
    src/stabilizer_tableau.cpp
    src/mps_sampler.cpp
    src/cq_qasm_parser.cpp
    src/algebra/ring.cpp
    src/stabilizer/tableau.cpp
    src/vulkan/vulkan_engine.cpp
)
target_include_directories(cq_hecs_core PUBLIC include src)
target_link_libraries(cq_hecs_core PRIVATE ${Vulkan_LIBRARIES})
set_target_properties(cq_hecs_core PROPERTIES OUTPUT_NAME "cq_hecs_core")
if(CQ_HAVE_VULKAN)
    target_compile_definitions(cq_hecs_core PRIVATE CQ_NATIVE_VULKAN=1)
else()
    target_compile_definitions(cq_hecs_core PRIVATE CQ_NATIVE_VULKAN=0)
endif()
if(TARGET vulkan_shaders)
    add_dependencies(cq_hecs_core vulkan_shaders)
endif()

# 6. Test Executables
add_executable(test_bitexact_and_stress tests/test_bitexact_and_stress.cpp)
target_include_directories(test_bitexact_and_stress PRIVATE include src)
target_link_libraries(test_bitexact_and_stress PRIVATE ${Vulkan_LIBRARIES})

add_executable(test_exact_algebra tests/test_exact_algebra.cpp)
target_include_directories(test_exact_algebra PRIVATE include src)
target_link_libraries(test_exact_algebra PRIVATE ${Vulkan_LIBRARIES})

add_executable(test_stabilizer tests/test_stabilizer.cpp src/stabilizer_tableau.cpp)
target_include_directories(test_stabilizer PRIVATE include src)
target_link_libraries(test_stabilizer PRIVATE ${Vulkan_LIBRARIES})

add_executable(test_hybrid_mps tests/test_hybrid_mps.cpp src/hybrid_engine.cpp src/stabilizer_tableau.cpp)
target_include_directories(test_hybrid_mps PRIVATE include src)
target_link_libraries(test_hybrid_mps PRIVATE ${Vulkan_LIBRARIES})

add_executable(test_stress_limits tests/test_stress_limits.cpp src/mps_sampler.cpp)
target_include_directories(test_stress_limits PRIVATE include src)
target_link_libraries(test_stress_limits PRIVATE ${Vulkan_LIBRARIES})

add_executable(test_exact_ring tests/cpp/test_exact_ring.cpp src/algebra/ring.cpp)
target_include_directories(test_exact_ring PRIVATE include src)
target_link_libraries(test_exact_ring PRIVATE ${Vulkan_LIBRARIES})

add_executable(test_stabilizer_extreme tests/cpp/test_stabilizer_extreme.cpp src/stabilizer/tableau.cpp)
target_include_directories(test_stabilizer_extreme PRIVATE include src)
target_link_libraries(test_stabilizer_extreme PRIVATE ${Vulkan_LIBRARIES})

add_executable(test_300q_stress tests/cpp/test_300q_stress.cpp src/vulkan/vulkan_engine.cpp)
target_include_directories(test_300q_stress PRIVATE include src)
target_link_libraries(test_300q_stress PRIVATE ${Vulkan_LIBRARIES})

if(CQ_HAVE_VULKAN)
add_executable(test_qasm_contract tests/test_qasm_contract.cpp $<TARGET_OBJECTS:cq_hecs_core_objects>)
target_link_libraries(test_qasm_contract PRIVATE ${Vulkan_LIBRARIES})
endif()

add_executable(test_sat_parser tests/cpp/test_sat_parser.cpp $<TARGET_OBJECTS:cq_hecs_cpu_objects>)
target_include_directories(test_sat_parser PRIVATE include src)
# A deliberately false assertion must abort even in Release (GEMINI.md 3.5).
add_executable(test_release_assert_meta tests/cpp/test_release_assert_meta.cpp)
add_executable(test_vulkan_device_policy tests/cpp/test_vulkan_device_policy.cpp)
target_include_directories(test_vulkan_device_policy PRIVATE ${CMAKE_SOURCE_DIR}/include)
target_link_libraries(test_sat_parser PRIVATE ${Vulkan_LIBRARIES})

add_executable(test_statevector_contract tests/cpp/test_statevector_contract.cpp)
target_include_directories(test_statevector_contract PRIVATE include src)
target_link_libraries(test_statevector_contract PRIVATE ${Vulkan_LIBRARIES})

add_executable(test_mps_contract tests/cpp/test_mps_contract.cpp)
target_include_directories(test_mps_contract PRIVATE include src)
target_link_libraries(test_mps_contract PRIVATE ${Vulkan_LIBRARIES})

add_executable(test_qpu_facade_contract tests/cpp/test_qpu_facade_contract.cpp)
target_include_directories(test_qpu_facade_contract PRIVATE include src)
target_link_libraries(test_qpu_facade_contract PRIVATE ${Vulkan_LIBRARIES})

if(CQ_HAVE_VULKAN)
add_executable(test_vulkan_compute_contract tests/cpp/test_vulkan_compute_contract.cpp $<TARGET_OBJECTS:cq_hecs_core_objects>)
target_include_directories(test_vulkan_compute_contract PRIVATE include src)
target_link_libraries(test_vulkan_compute_contract PRIVATE ${Vulkan_LIBRARIES})

# W4-17/T6-04: fault-injection and CPU-vs-Vulkan differential tests. Both compile
# the C-ABI facade (src/cq_hecs_api.cpp) INTO the test executable, not the DLL:
# the fault-injection table is a C++-only seam, and a separate module would own
# a separate table. CQ_HECS_STATIC removes the dllimport decoration.
foreach(_vk_test IN ITEMS test_vulkan_fault_injection test_vulkan_bcp_differential)
    add_executable(${_vk_test} tests/cpp/${_vk_test}.cpp src/cq_hecs_api.cpp $<TARGET_OBJECTS:cq_hecs_core_objects>)
    target_include_directories(${_vk_test} PRIVATE include src)
    target_compile_definitions(${_vk_test} PRIVATE CQ_HECS_STATIC=1)
    target_link_libraries(${_vk_test} PRIVATE ${Vulkan_LIBRARIES})
endforeach()
endif()

# W4-18: C-ABI hardening contract for the CPU core library (also built CPU-only).
add_executable(test_c_abi_core tests/cpp/test_c_abi_core.cpp)
target_include_directories(test_c_abi_core PRIVATE include src)
target_link_libraries(test_c_abi_core PRIVATE cq_hecs_core)

# 7. CTest Verification Suite
enable_testing()
if(CQ_HAVE_VULKAN)
add_test(NAME test_reversibility COMMAND test_reversibility)
endif()
if(CQ_HAVE_VULKAN)
add_test(NAME test_ghz300 COMMAND test_ghz300)
endif()
if(CQ_HAVE_VULKAN)
add_test(NAME test_constraint_solver COMMAND test_constraint_solver)
endif()
if(CQ_HAVE_VULKAN)
add_test(NAME cq_hecs_cpp_hardening COMMAND test_engine_cpp)
endif()
if(CQ_HAVE_VULKAN)
add_test(NAME cq_hecs_full_verification COMMAND cq_hecs test)
endif()
add_test(NAME test_bitexact_and_stress COMMAND test_bitexact_and_stress)
add_test(NAME test_exact_algebra COMMAND test_exact_algebra)
add_test(NAME test_stabilizer COMMAND test_stabilizer)
add_test(NAME test_hybrid_mps COMMAND test_hybrid_mps)
add_test(NAME test_stress_limits COMMAND test_stress_limits)
add_test(NAME test_exact_ring COMMAND test_exact_ring)
add_test(NAME test_stabilizer_extreme COMMAND test_stabilizer_extreme)
add_test(NAME test_300q_stress COMMAND test_300q_stress)
if(CQ_HAVE_VULKAN)
add_test(NAME test_qasm_contract COMMAND test_qasm_contract)
endif()
add_test(NAME test_sat_parser COMMAND test_sat_parser)
add_test(NAME test_release_assert_meta COMMAND test_release_assert_meta)
set_tests_properties(test_release_assert_meta PROPERTIES WILL_FAIL TRUE)
add_test(NAME test_vulkan_device_policy COMMAND test_vulkan_device_policy)
add_test(NAME test_statevector_contract COMMAND test_statevector_contract)
add_test(NAME test_mps_contract COMMAND test_mps_contract)
add_test(NAME test_qpu_facade_contract COMMAND test_qpu_facade_contract)
if(CQ_HAVE_VULKAN)
add_test(NAME test_vulkan_compute_contract COMMAND test_vulkan_compute_contract)
set_tests_properties(test_vulkan_compute_contract PROPERTIES SKIP_RETURN_CODE 77)
# "init"/"validate" modes need no GPU (injected failures / pre-device validation);
# the "device" modes exit 77 (SKIPPED, never PASSED) when no Vulkan device exists.
add_test(NAME test_vulkan_fault_init COMMAND test_vulkan_fault_injection init)
add_test(NAME test_vulkan_fault_device COMMAND test_vulkan_fault_injection device)
set_tests_properties(test_vulkan_fault_device PROPERTIES SKIP_RETURN_CODE 77)
add_test(NAME test_vulkan_bcp_validation COMMAND test_vulkan_bcp_differential validate)
add_test(NAME test_vulkan_bcp_differential COMMAND test_vulkan_bcp_differential device)
set_tests_properties(test_vulkan_bcp_differential PROPERTIES SKIP_RETURN_CODE 77)
endif()
add_test(NAME test_c_abi_core COMMAND test_c_abi_core)

# 8. Nanobind Python C++20 Modules
find_package(Python 3.11 COMPONENTS Interpreter Development.Module QUIET)
if(Python_FOUND)
    execute_process(
        COMMAND "${Python_EXECUTABLE}" -m nanobind --cmake_dir
        OUTPUT_VARIABLE NB_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
    )
    if(EXISTS "${NB_DIR}")
        list(APPEND CMAKE_PREFIX_PATH "${NB_DIR}")
        find_package(nanobind CONFIG QUIET)
        if(nanobind_FOUND)
            nanobind_add_module(_cq_hecs_core python/binding.cpp)
            target_include_directories(_cq_hecs_core PRIVATE include src)
            target_link_libraries(_cq_hecs_core PRIVATE ${Vulkan_LIBRARIES})

            nanobind_add_module(_cqhecs_core python/cqhecs_bindings.cpp
                src/stabilizer_tableau.cpp
                src/mps_sampler.cpp
                src/hybrid_engine.cpp
                src/cq_qasm_parser.cpp
            )
            target_include_directories(_cqhecs_core PRIVATE include src)
            target_link_libraries(_cqhecs_core PRIVATE ${Vulkan_LIBRARIES})
            
            set_target_properties(_cq_hecs_core _cqhecs_core PROPERTIES
                LIBRARY_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/python"
                RUNTIME_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/python"
            )
        endif()
    endif()
endif()
