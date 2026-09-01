cmake_minimum_required(VERSION 3.24)
project(CQ_HECS VERSION 0.2.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Ensure output goes to bin/ and bin/Release/
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/bin)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_SOURCE_DIR}/bin/Release)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_RELEASE ${CMAKE_SOURCE_DIR}/bin/Release)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_SOURCE_DIR}/bin)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_RELEASE ${CMAKE_SOURCE_DIR}/bin/Release)

if(MSVC)
    add_compile_options(/W4 /permissive- /Zc:preprocessor)
else()
    add_compile_options(-Wall -Wextra)
endif()

option(CQ_ENABLE_AVX2 "Enable AVX2 SIMD optimizations" OFF)
if(CQ_ENABLE_AVX2)
    if(MSVC)
        add_compile_options(/arch:AVX2)
    else()
        add_compile_options(-mavx2)
    endif()
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
        file(GLOB_RECURSE _FOUND_VULKAN_H "$ENV{VULKAN_SDK}/*/vulkan.h" "$ENV{VULKAN_SDK}/vulkan.h")
        if(_FOUND_VULKAN_H)
            list(GET _FOUND_VULKAN_H 0 _VULKAN_H_PATH)
            get_filename_component(_VULKAN_DIR ${_VULKAN_H_PATH} DIRECTORY)
            get_filename_component(_VULKAN_INC ${_VULKAN_DIR} DIRECTORY)
            set(Vulkan_INCLUDE_DIR "${_VULKAN_INC}" CACHE PATH "Vulkan include directory" FORCE)
            message(STATUS "Found Vulkan header at ${_VULKAN_H_PATH}, setting Vulkan_INCLUDE_DIR=${_VULKAN_INC}")
        endif()

        file(GLOB_RECURSE _FOUND_VULKAN_LIB "$ENV{VULKAN_SDK}/*vulkan-1.lib" "$ENV{VULKAN_SDK}/*vulkan.lib")
        if(_FOUND_VULKAN_LIB)
            list(GET _FOUND_VULKAN_LIB 0 _VULKAN_LIB_PATH)
            set(Vulkan_LIBRARY "${_VULKAN_LIB_PATH}" CACHE FILEPATH "Vulkan library" FORCE)
            message(STATUS "Found Vulkan library at ${_VULKAN_LIB_PATH}, setting Vulkan_LIBRARY=${_VULKAN_LIB_PATH}")
        endif()
    endif()
endif()

find_package(Vulkan REQUIRED)

# -----------------------------------------------------------------------------
# Automated Vulkan 1.3 SPIR-V Shader Compilation Target (glslangValidator)
# -----------------------------------------------------------------------------
find_program(GLSLANG_VALIDATOR glslangValidator HINTS "$ENV{VULKAN_SDK}/bin")
if(GLSLANG_VALIDATOR)
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
else()
    message(WARNING "glslangValidator not found. Using pre-compiled SPIR-V shaders.")
endif()

include_directories(
    include
    src
    ${Vulkan_INCLUDE_DIRS}
)

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

# 1. Standalone Monolithic Executable (CLI)
add_executable(cq_hecs src/main.cpp ${CORE_SOURCES} ${CORE_HEADERS})
target_link_libraries(cq_hecs PRIVATE ${Vulkan_LIBRARIES})
if(TARGET vulkan_shaders)
    add_dependencies(cq_hecs vulkan_shaders)
endif()

# 2. C-ABI Shared Library (cq_hecs.dll / libcq_hecs.so)
add_library(cq_hecs_shared SHARED src/cq_hecs_api.cpp ${CORE_SOURCES} ${CORE_HEADERS})
set_target_properties(cq_hecs_shared PROPERTIES
    OUTPUT_NAME "cq_hecs"
    DEFINE_SYMBOL "CQ_HECS_EXPORTS"
)
target_link_libraries(cq_hecs_shared PRIVATE ${Vulkan_LIBRARIES})
if(TARGET vulkan_shaders)
    add_dependencies(cq_hecs_shared vulkan_shaders)
endif()

# 3. Deterministic Test Executables
add_executable(test_reversibility tests/test_reversibility.cpp ${VRTS_SOURCES} ${VRTS_HEADERS})
target_link_libraries(test_reversibility PRIVATE ${Vulkan_LIBRARIES})

add_executable(test_ghz300 tests/test_ghz300.cpp ${VRTS_SOURCES} ${VRTS_HEADERS})
target_link_libraries(test_ghz300 PRIVATE ${Vulkan_LIBRARIES})

add_executable(test_constraint_solver tests/test_constraint_solver.cpp ${VRTS_SOURCES} ${VRTS_HEADERS})
target_link_libraries(test_constraint_solver PRIVATE ${Vulkan_LIBRARIES})

add_executable(test_engine_cpp tests/test_engine_cpp.cpp ${CORE_SOURCES} ${CORE_HEADERS})
target_link_libraries(test_engine_cpp PRIVATE ${Vulkan_LIBRARIES})

# 4. Examples
add_executable(ghz300_example examples/ghz300_example.cpp ${VRTS_SOURCES} ${VRTS_HEADERS})
target_link_libraries(ghz300_example PRIVATE ${Vulkan_LIBRARIES})

add_executable(maxcut_example examples/maxcut_example.cpp ${VRTS_SOURCES} ${VRTS_HEADERS})
target_link_libraries(maxcut_example PRIVATE ${Vulkan_LIBRARIES})

option(CQ_BUILD_TESTS "Build test suite" ON)
option(CQHECS_BUILD_TESTS "Build test suite" ON)
option(CQHECS_HEADLESS "Enable Headless SwiftShader / Software Vulkan ICD" OFF)
option(CQ_ENABLE_SANITIZERS "Enable Address and UB sanitizers" OFF)

if(CQHECS_HEADLESS)
    add_compile_definitions(CQHECS_HEADLESS=1)
endif()

if(CQ_ENABLE_SANITIZERS AND CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
    add_link_options(-fsanitize=address,undefined)
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

# 7. CTest Verification Suite
enable_testing()
add_test(NAME test_reversibility COMMAND test_reversibility)
add_test(NAME test_ghz300 COMMAND test_ghz300)
add_test(NAME test_constraint_solver COMMAND test_constraint_solver)
add_test(NAME cq_hecs_cpp_hardening COMMAND test_engine_cpp)
add_test(NAME cq_hecs_full_verification COMMAND cq_hecs test)
add_test(NAME test_bitexact_and_stress COMMAND test_bitexact_and_stress)
add_test(NAME test_exact_algebra COMMAND test_exact_algebra)
add_test(NAME test_stabilizer COMMAND test_stabilizer)
add_test(NAME test_hybrid_mps COMMAND test_hybrid_mps)
add_test(NAME test_stress_limits COMMAND test_stress_limits)
add_test(NAME test_exact_ring COMMAND test_exact_ring)
add_test(NAME test_stabilizer_extreme COMMAND test_stabilizer_extreme)
add_test(NAME test_300q_stress COMMAND test_300q_stress)

# 8. Nanobind Python C++20 Modules
find_package(Python 3.10 COMPONENTS Interpreter Development.Module QUIET)
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
