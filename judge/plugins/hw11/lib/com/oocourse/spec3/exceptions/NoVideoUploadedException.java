package com.oocourse.spec3.exceptions;

/**
 * {@code NoVideoUploadedException} 类用于表示当系统没有已上传的视频时抛出的异常。
 *
 * <p>异常统计信息的格式为：nvu-{@code x}，
 * 其中 {@code x} 为此类异常发生的总次数。</p>
 */
public class NoVideoUploadedException extends MyException {
    private static int count = 0;

    /**
     * 构造一个新的 {@code NoVideoUploadedException} 实例。
     *
     */
    public NoVideoUploadedException() {
        count++;
    }

    /**
     * 输出异常的统计信息到标准输出。
     * 格式为：nvu-{@code x}，
     * 其中 {@code x} 为此类异常发生的总次数。
     */
    public void print() {
        System.out.println("nvu-" + count);
    }
}
