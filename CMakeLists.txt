cmake_minimum_required(VERSION 3.24)
project(CQ_HECS VERSION 2.0.0 LANGUAGES CXX)

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
endif()

find_package(Vulkan REQUIRED)

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

# 2. C-ABI Shared Library (cq_hecs.dll / libcq_hecs.so)
add_library(cq_hecs_shared SHARED src/cq_hecs_api.cpp ${CORE_SOURCES} ${CORE_HEADERS})
set_target_properties(cq_hecs_shared PROPERTIES
    OUTPUT_NAME "cq_hecs"
    DEFINE_SYMBOL "CQ_HECS_EXPORTS"
)
target_link_libraries(cq_hecs_shared PRIVATE ${Vulkan_LIBRARIES})

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

# 5. CTest Verification Suite
enable_testing()
add_test(NAME test_reversibility COMMAND test_reversibility)
add_test(NAME test_ghz300 COMMAND test_ghz300)
add_test(NAME test_constraint_solver COMMAND test_constraint_solver)
add_test(NAME cq_hecs_cpp_hardening COMMAND test_engine_cpp)
add_test(NAME cq_hecs_full_verification COMMAND cq_hecs test)

