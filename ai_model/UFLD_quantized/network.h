

#ifndef __NETWORK_H__
#define __NETWORK_H__

/*
    Openedges Enlight Network Compiler
*/

#include "enlight_data_type.h"
#include "enlight_network.h"
#ifdef BARE_METAL_FW_DEV
#    include "npu_cmd.h"
#endif


static enlight_act_tensor_t Input_0 = {
    ENLIGHT_DTYPE_INT8,
    (void*)0x0,
    0x0,
    691200,
    3,
    4,
    {1, 3, 288, 800},
    128.0000,
    0,
    0,
    "Input_0",
};

static enlight_act_tensor_t ReLU_0 = {
    ENLIGHT_DTYPE_INT8,
    (void*)0x0,
    0xe1000,
    3686400,
    2,
    4,
    {1, 64, 144, 400},
    36.9710,
    0,
    0,
    "ReLU_0",
};

static enlight_act_tensor_t MaxPool2d_0 = {
    ENLIGHT_DTYPE_INT8,
    (void*)0x0,
    0x0,
    921600,
    2,
    4,
    {1, 64, 72, 200},
    36.9710,
    0,
    0,
    "MaxPool2d_0",
};

static enlight_act_tensor_t ReLU_4 = {
    ENLIGHT_DTYPE_INT8,
    (void*)0x0,
    0xe1000,
    921600,
    2,
    4,
    {1, 64, 72, 200},
    23.9647,
    0,
    0,
    "ReLU_4",
};

static enlight_act_tensor_t ReLU_6 = {
    ENLIGHT_DTYPE_INT8,
    (void*)0x0,
    0x0,
    460800,
    2,
    4,
    {1, 128, 36, 100},
    39.2850,
    0,
    0,
    "ReLU_6",
};

static enlight_act_tensor_t ReLU_8 = {
    ENLIGHT_DTYPE_INT8,
    (void*)0x0,
    0x70800,
    460800,
    2,
    4,
    {1, 128, 36, 100},
    34.6244,
    0,
    0,
    "ReLU_8",
};

static enlight_act_tensor_t ReLU_10 = {
    ENLIGHT_DTYPE_INT8,
    (void*)0x0,
    0x0,
    230400,
    2,
    4,
    {1, 256, 18, 50},
    64.5315,
    0,
    0,
    "ReLU_10",
};

static enlight_act_tensor_t ReLU_12 = {
    ENLIGHT_DTYPE_INT8,
    (void*)0x0,
    0x38400,
    230400,
    2,
    4,
    {1, 256, 18, 50},
    56.8800,
    0,
    0,
    "ReLU_12",
};

static enlight_act_tensor_t ReLU_14 = {
    ENLIGHT_DTYPE_INT8,
    (void*)0x0,
    0x0,
    115200,
    2,
    4,
    {1, 512, 9, 25},
    146.1150,
    0,
    0,
    "ReLU_14",
};

static enlight_act_tensor_t ReLU_16 = {
    ENLIGHT_DTYPE_INT8,
    (void*)0x0,
    0x1c200,
    115200,
    2,
    4,
    {1, 512, 9, 25},
    39.8929,
    0,
    0,
    "ReLU_16",
};

static enlight_act_tensor_t Conv2d_20 = {
    ENLIGHT_DTYPE_INT8,
    (void*)0x0,
    0x0,
    7200,
    2,
    4,
    {1, 8, 9, 25},
    4.1641,
    0,
    0,
    "Conv2d_20",
};

static enlight_act_tensor_t Reshape_1 = {
    ENLIGHT_DTYPE_INT8,
    (void*)0x0,
    0x1c20,
    1824,
    2,
    4,
    {1, 1800, 1, 1},
    4.1641,
    0,
    0,
    "Reshape_1",
};

static enlight_act_tensor_t Linear_1 = {
    ENLIGHT_DTYPE_INT8,
    (void*)0x0,
    0x0,
    14496,
    4,
    4,
    {1, 14472, 1, 1},
    5.9019,
    0,
    1,
    "Linear_1",
};

/* Buf description of Activation and Output*/
static enlight_act_tensor_t* all_output_tensors[13] = {
    &Input_0,
    &ReLU_0,
    &MaxPool2d_0,
    &ReLU_4,
    &ReLU_6,
    &ReLU_8,
    &ReLU_10,
    &ReLU_12,
    &ReLU_14,
    &ReLU_16,
    &Conv2d_20,
    &Reshape_1,
    &Linear_1,
};


static enlight_custom_postproc_t post_ext_param = {
    {&Linear_1,},
    1,
};

static enlight_buf_size_t network_buf_size = {
    //code_buf_size
    0x10600, 
    //wght_buf_size
    0x2aa6600, 
    //input_buf_size
    0xa8c00, 
    //output_buf_size
    0x38a0, 
    //work_buf_size
    0x465000, 
};

enlight_network_t network_instance = {
    //network_name
    "UFLD_quantized.enlight",
    //post_proc
    ENLIGHT_POST_CUSTOM,
    //batch_size
    1,
    //img_sizes
    {3, 288, 800},
    //buf_sizes
    &network_buf_size,
    //post_proc_extension
    (void*)&post_ext_param,
    //output_tensors_num
    1,
    //output_tensors
    {&Linear_1,},
    //Conv MAC num
    9231814656,

    //For Debug only
    //all_tensors_num,
    199,
    //all_tensors
    all_output_tensors,

    // For toolkit developer
#ifdef BARE_METAL_FW_DEV
    //npu_cmd_codes
    npu_cmd,
#endif
};

#endif /*__NETWORK_H__*/