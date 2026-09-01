cmake_minimum_required(VERSION 3.20)
project(CQ_HECS VERSION 4.0 LANGUAGES CXX)

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
endif()

find_package(Vulkan REQUIRED)

include_directories(
    include
    src
    ${Vulkan_INCLUDE_DIRS}
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
)

# 1. Standalone Monolithic Executable
add_executable(cq_hecs src/main.cpp ${CORE_SOURCES} ${CORE_HEADERS})
target_link_libraries(cq_hecs PRIVATE ${Vulkan_LIBRARIES})

# 2. C-ABI Shared Library (cq_hecs.dll)
add_library(cq_hecs_shared SHARED src/cq_hecs_api.cpp ${CORE_SOURCES} ${CORE_HEADERS})
set_target_properties(cq_hecs_shared PROPERTIES
    OUTPUT_NAME "cq_hecs"
    DEFINE_SYMBOL "CQ_HECS_EXPORTS"
)
target_link_libraries(cq_hecs_shared PRIVATE ${Vulkan_LIBRARIES})

# 3. Native C++ Hardening Test Executable
add_executable(test_engine_cpp tests/test_engine_cpp.cpp ${CORE_SOURCES} ${CORE_HEADERS})
target_link_libraries(test_engine_cpp PRIVATE ${Vulkan_LIBRARIES})

# Embedded shaders eliminate runtime file dependency!
enable_testing()
add_test(NAME cq_hecs_full_verification COMMAND cq_hecs test)
add_test(NAME cq_hecs_cpp_hardening COMMAND test_engine_cpp)
