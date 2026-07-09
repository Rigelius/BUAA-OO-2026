package com.oocourse.spec1.main;

import com.oocourse.spec1.exceptions.DuplicateSubscriptionException;
import com.oocourse.spec1.exceptions.EqualUserIdException;
import com.oocourse.spec1.exceptions.EqualVideoIdException;
import com.oocourse.spec1.exceptions.FollowLinkNotFoundException;
import com.oocourse.spec1.exceptions.InvalidAgeException;
import com.oocourse.spec1.exceptions.SelfSubscriptionException;
import com.oocourse.spec1.exceptions.UncessException;
import com.oocourse.spec1.exceptions.UserIdNotFoundException;
import com.oocourse.spec1.exceptions.VideoIdNotFoundException;

import java.util.List;

public interface NetworkInterface {

    /*@ public instance model non_null UserInterface[] users;
      @ public instance model non_null VideoInterface[] videos;
      @*/

    /*@ invariant (\forall int i,j; 0 <= i && i < j && j < users.length;
      @               !users[i].equals(users[j])) &&
      @           (\forall int i,j; 0 <= i && i < j && j < videos.length;
      @               !videos[i].equals(videos[j]));
      @*/
    
    //@ ensures \result == (\exists int i; 0 <= i && i < users.length; users[i].getId() == id);
    public /*@ pure @*/ boolean containsUser(int id);
    
    /*@ public normal_behavior
      @ requires containsUser(id);
      @ ensures (\exists int i; 0 <= i && i < users.length; users[i].getId() == id && \result == users[i]);
      @ also
      @ public normal_behavior
      @ requires !containsUser(id);
      @ ensures \result == null;
      @*/
    public /*@ pure @*/ UserInterface getUser(int id);

    //@ ensures \result == (\exists int i; 0 <= i && i < videos.length; videos[i].getId() == id);
    public /*@ pure @*/ boolean containsVideo(int id);

    /*@ public normal_behavior
      @ requires containsVideo(id);
      @ ensures (\exists int i; 0 <= i && i < videos.length; videos[i].getId() == id && \result == videos[i]);
      @ also
      @ public normal_behavior
      @ requires !containsVideo(id);
      @ ensures \result == null;
      @*/
    public /*@ pure @*/ VideoInterface getVideo(int id);
    
    /*@ public normal_behavior
      @ requires !containsUser(id) && age >= 0 && age <= 110;
      @ assignable users;
      @ ensures containsUser(id);
      @ ensures getUser(id).getId() == id;
      @ ensures getUser(id).getName().equals(name);
      @ ensures getUser(id).getAge() == age;
      @ ensures getUser(id).following.length == 0;
      @ ensures getUser(id).followers.length == 0;
      @ ensures getUser(id).receivedVideos.length == 0;
      @ ensures users.length == \old(users.length) + 1;
      @ ensures (\forall int i; 0 <= i && i < \old(users.length);
      @              (\exists int j; 0 <= j && j < users.length;
      @                  users[j] == \old(users[i])));
      @ ensures (* output-> "add_user succeeded" *);
      @ also
      @ public exceptional_behavior
      @ signals (EqualUserIdException e) containsUser(id);
      @ signals (InvalidAgeException e) !containsUser(id) && (age < 0 || age > 110);
      @*/
    public /*@ safe @*/ void addUser(int id, String name, int age) throws EqualUserIdException, InvalidAgeException;
    
    /*@ public normal_behavior
      @ requires containsUser(uploaderId) && !containsVideo(videoId);
      @ assignable videos, users[*].receivedVideos;
      @ ensures containsVideo(videoId);
      @ ensures getVideo(videoId).getId() == videoId;
      @ ensures getVideo(videoId).getUploaderId() == uploaderId;
      @ ensures (\forall UserInterface u; getUser(uploaderId).containsFollower(u); u.receivedVideos.get(0).equals(VideoId));
      @ ensures (\forall UserInterface u; getUser(uploaderId).containsFollower(u); (\forall int i; 0 <= i && i < \old(u.receivedVideos.length);
      @                                                                         u.receivedVideos.get(i + 1) == \old(u.receivedVideos.get(i))));
      @ ensures (\forall UserInterface u; getUser(uploaderId).containsFollower(u); u.receivedVideos.length == \old(u.receivedVideos.length) + 1);
      @ ensures (* output-> "upload_video succeeded" *);
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(uploaderId);
      @ signals (EqualVideoIdException e) containsUser(uploaderId) && containsVideo(videoId);
      @*/
    public /*@ safe @*/ void uploadVideo(int uploaderId, int videoId) throws UserIdNotFoundException, EqualVideoIdException;
    
    /*@ public normal_behavior
      @ requires containsUser(id1) && containsUser(id2) && id1 != id2 && !getUser(id1).isFollowing(getUser(id2));
      @ assignable users[*];
      @ ensures getUser(id1).isFollowing(getUser(id2));
      @ ensures getUser(id2).containsFollower(getUser(id1));
      @ ensures (* output-> "follow_user succeeded" *);
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(id1);
      @ signals (UserIdNotFoundException e) containsUser(id1) && !containsUser(id2);
      @ signals (SelfSubscriptionException e) containsUser(id1) && containsUser(id2) && id1 == id2;
      @ signals (DuplicateSubscriptionException e) containsUser(id1) && containsUser(id2) && id1 != id2 && getUser(id1).isFollowing(getUser(id2));
      @*/
    public /*@ safe @*/ void followUser(int id1, int id2) throws UserIdNotFoundException, SelfSubscriptionException, DuplicateSubscriptionException;
    
    /*@ public normal_behavior
      @ requires containsUser(id1) && containsUser(id2) && getUser(id1).isFollowing(getUser(id2));
      @ assignable users[*];
      @ ensures !getUser(id1).isFollowing(getUser(id2));
      @ ensures !getUser(id2).containsFollower(getUser(id1));
      @ ensures (* output-> "unfollow_user succeeded" *);
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(id1);
      @ signals (UserIdNotFoundException e) containsUser(id1) && !containsUser(id2);
      @ signals (FollowLinkNotFoundException e) containsUser(id1) && containsUser(id2) && !getUser(id1).isFollowing(getUser(id2));
      @*/
    public /*@ safe @*/ void unfollowUser(int id1, int id2) throws UserIdNotFoundException, FollowLinkNotFoundException;
    
    /*@ public normal_behavior
      @ requires containsUser(userId) && containsVideo(videoId);
      @ assignable getUser(userId).receivedVideos;
      @ ensures !getUser(userId).hasReceivedVideo(getVideo(videoId));
      @ ensures (* output-> "watch_video succeeded");
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(userId);
      @ signals (VideoIdNotFoundException e) containsUser(userId) && !containsVideo(videoId);
      @*/
    public /*@ safe @*/ void watchVideo(int userId, int videoId) throws UserIdNotFoundException, VideoIdNotFoundException;
    
    /*@ public normal_behavior
      @ requires containsUser(userId);
      @ assignable \nothing;
      @ ensures \result == getUser(userId).queryReceivedUnwatchedVideos();
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(userId);
      @*/
    public /*@ safe @*/ List<Integer> queryReceivedUnwatchedVideos(int userId) throws UserIdNotFoundException;
    
    /*@ public normal_behavior
      @ requires containsUser(upId);
      @ assignable \nothing;
      @ ensures \result == getUser(upId).queryAgeRatio();
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(upId);
      @*/
    public /*@ safe @*/ double[] queryUpFollowersAgeRatio(int upId) throws UserIdNotFoundException;
    
    /*@ ensures \result == (\sum int i; 0 <= i && i < users.length;
      @          (\sum int j; i < j && j < users.length;
      @           (users[i].isFollowing(users[j]) && users[j].isFollowing(users[i])) ? 1 : 0));
      @*/
    public /*@ pure @*/ int queryMutualFollowingSum();
    
    /*@ public normal_behavior
      @ requires containsUser(id1) && id1 == id2;
      @ ensures \result == 0;
      @ also
      @ public normal_behavior
      @ requires containsUser(id1) &&
      @          containsUser(id2) &&
      @          id1 != id2 &&
      @          (\exists UserInterface[] path;
      @          path.length >= 2 &&
      @          path[0].equals(getUser(id1)) &&
      @          path[path.length - 1].equals(getUser(id2)) &&
      @          (\forall int i; 1 <= i && i < path.length; path[i - 1].isFollowing(path[i])));
      @ ensures  (\exists UserInterface[] pathM;
      @          pathM.length >= 2 &&
      @          pathM[0].equals(getUser(id1)) &&
      @          pathM[pathM.length - 1].equals(getUser(id2)) &&
      @          (\forall int i; 1 <= i && i < pathM.length; pathM[i - 1].isFollowing(pathM[i]));
      @          (\forall UserInterface[] path;
      @          path.length >= 2 &&
      @          path[0].equals(getUser(id1)) &&
      @          path[path.length - 1].equals(getUser(id2)) &&
      @          (\forall int i; 1 <= i && i < path.length; path[i - 1].isFollowing(path[i]));
      @          (\sum int i; 0 <= i && i < path.length; 1) >=
      @          (\sum int i; 0 <= i && i < pathM.length; 1)) &&
      @          \result==(\sum int i; 1 <= i && i < pathM.length; 1));
      @ also
      @ public exceptional_behavior
      @ signals (UserIdNotFoundException e) !containsUser(id1);
      @ signals (UserIdNotFoundException e) containsUser(id1) &&
      @                                       !containsUser(id2);
      @ signals (UncessException e) containsUser(id1) &&
      @                                   containsUser(id2) &&
      @         !(\exists UserInterface[] path;
      @         path.length >= 2 &&
      @         path[0].equals(getUser(id1)) &&
      @         path[path.length - 1].equals(getUser(id2));
      @         (\forall int i; 1 <= i && i < path.length; path[i - 1].isFollowing(path[i])));
      @*/

    public /*@ pure @*/ int queryShortestPath(int id1, int id2) throws UserIdNotFoundException, UncessException;
    
}
