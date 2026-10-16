cmake_minimum_required(VERSION 3.22)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
# As ESP-IDF's own examples have it: only main and what main names is built.
# The linux target needs it, and it is the case where main has to name demo.
idf_build_set_property(MINIMAL_BUILD ON)
project(app)
