var app = angular.module('mainApp', ['ui.router' , 'ui.bootstrap' , 'ngResource'], function($interpolateProvider) {
    $interpolateProvider.startSymbol('{[{');
    $interpolateProvider.endSymbol('}]}');
  });

app.config(function($stateProvider, $urlRouterProvider) {

    $urlRouterProvider.otherwise('');

    $stateProvider.state('index', {
        url         : '',
        templateUrl : '/dashboard',
        controller  : 'mainCtrl'
    })
    .state('productdashboard', {
        url         : '/product/:productId',
        templateUrl : function(urlattr){
            return '/product/' + urlattr.productId + '/dashboard';
        },
        controller  : 'prodController'
    })
    .state('productstationroot', {
        url         : '/product/:productId/station/:stationId',
        templateUrl : function($stateParams){
            return '/product/' + $stateParams.productId + '/station/' + $stateParams.stationId;
        },
        resolve:{
            productId: function($stateParams){
                return $stateParams.productId;
            },
            stationId: function($stateParams){
                return $stateParams.stationId;
            }
        },
        controller  : 'statController'
    })
});

app.factory('songList', function($http, $q){
    var d = $q.defer();
    $http.get('/DocumentsList').success(function(data){
        d.resolve(data);
    });
    return d.promise;
});

app.controller('mainCtrl', ['$scope', '$resource', '$http', function($scope, $resource, $http) {

    var Issue = $resource('http://localhost:5000/api/playlist/get');
    $scope.songs = Issue.query();
    $scope.songs.$promise.then(function(){
        $scope.totalItems = $scope.songs.length;
    });
    $scope.currentPage = 1;
    $scope.numPerPage = 10;

    console.log($scope.songs)

    //$scope.songs = []

    $scope.searchtext = function() {
        var searchapi = 'http://localhost:5000/api/search/text/' + $scope.searchstring;
        var NewIssue = $resource(searchapi);
        $scope.songs.length = 0;
        $scope.songs = NewIssue.query();
        $scope.songs.$promise.then(function(){
            $scope.totalItems = $scope.songs.length;
            console.log($scope.totalItems);
        });
        $scope.currentPage = 1;
        $scope.numPerPage = 10;
    };

    $scope.searchnext = function() {
        var searchapi = 'http://localhost:5000/api/search/searchnext';
        var NewIssue = $resource(searchapi);
        $scope.songs.length = 0;
        $scope.songs = NewIssue.query();
        $scope.songs.$promise.then(function(){
            $scope.totalItems = $scope.songs.length;
            console.log($scope.totalItems);
        });
        $scope.currentPage = 1;
        $scope.numPerPage = 10;
    };

    $scope.searchprev = function() {
        var searchapi = 'http://localhost:5000/api/search/searchprev';
        var NewIssue = $resource(searchapi);
        $scope.songs.length = 0;
        $scope.songs = NewIssue.query();
        $scope.songs.$promise.then(function(){
            $scope.totalItems = $scope.songs.length;
            console.log($scope.totalItems);
        });
        $scope.currentPage = 1;
        $scope.numPerPage = 10;
    };

    $scope.addsong = function(songNum) {
        var searchapi = 'http://localhost:5000/api/playlist/add/' + songNum;
        var NewIssue = $resource(searchapi);
        $scope.songs.length = 0;
        $scope.songs = NewIssue.query();
        $scope.songs.$promise.then(function(){
            $scope.totalItems = $scope.songs.length;
            console.log($scope.totalItems);
        });
        $scope.currentPage = 1;
        $scope.numPerPage = 10;
    };

    $scope.stop = function(songNum) {
        var searchapi = 'http://localhost:5000/api/playlist/ctrl/stop';
        var NewIssue = $resource(searchapi);
        $scope.songs.length = 0;
        $scope.songs = NewIssue.query();
        $scope.songs.$promise.then(function(){
            $scope.totalItems = $scope.songs.length;
            console.log($scope.totalItems);
        });
        $scope.currentPage = 1;
        $scope.numPerPage = 10;
    };

    $scope.paginate = function(value) {
        var begin, end, index;
        begin = ($scope.currentPage - 1) * $scope.numPerPage;
        end = begin + $scope.numPerPage;
        index = $scope.songs.indexOf(value);
        return (begin <= index && index < end);
    };
}]);

app.controller('statController', function($scope, $http, $stateParams, $state) {
    $scope.init = function() {
        var buildsapi = 'http://localhost:5000/' + $stateParams.productId + '/' +$stateParams.stationId + '/buildsandtests';
        $http.get(buildsapi).then(
            function(response){
                $scope.builds = response.data;
                console.log($scope.builds)
                $scope.selectedBuild = $scope.builds[0];
                $scope.stationId = $stateParams.stationId;
                $scope.productId = $stateParams.productId;

                var testapi = 'http://localhost:5000/'+ $stateParams.productId +'/tests/' + $stateParams.stationId + '/build/' + $scope.selectedBuild;
                    $http.get(testapi).then(
                        function(response){
                            $scope.tests = response.data;
                            console.log($scope.tests)
                            $scope.selectedTest = $scope.tests[0];
                    } );
            })
    }
    $scope.selecttest = function(index) {
        $scope.selectedTest  = $scope.tests[index];
        $state.go("productstationroot.testid", {"buildid": $scope.selectedBuild, "testid": $scope.selectedTest})
    }
    $scope.selectbuild = function(index) {
        $scope.selectedBuild = $scope.builds[index];
        var testapi = 'http://localhost:5000/'+ $scope.productId +'/tests/' + $scope.stationId + '/build/' + $scope.selectedBuild;
            $http.get(testapi).then(
                function(response){
                    $scope.tests = response.data;
                    console.log($scope.tests)
                    $scope.selectedTest = $scope.tests[0];
            } );
    }
});

app.controller('corrController', function($scope, $http, $stateParams, $state) {
    $scope.init = function() {
        var buildsapi = 'http://localhost:5000/' + $stateParams.productId + '/corr/' +$stateParams.corrId + '/buildsandtests_corr';
        $http.get(buildsapi).then(
            function(response){
                $scope.builds = response.data;
                console.log($scope.builds)
                $scope.selectedBuild = $scope.builds[0];
                $scope.corrId = $stateParams.corrId;
                $scope.productId = $stateParams.productId;

                var testapi = 'http://localhost:5000/'+ $stateParams.productId +'/tests/corr/' + $stateParams.corrId + '/build/' + $scope.selectedBuild;
                    $http.get(testapi).then(
                        function(response){
                            $scope.tests = response.data;
                            console.log("hello")
                            console.log($scope.tests)
                            $scope.selectedTest = $scope.tests[0];
                    } );
            })
    }
    $scope.selecttest = function(index) {
        $scope.selectedTest  = $scope.tests[index];
        $state.go("productcorrroot.testid", {"buildid": $scope.selectedBuild, "testid": $scope.selectedTest})
    }
    $scope.selectbuild = function(index) {
        $scope.selectedBuild = $scope.builds[index];
        var testapi = 'http://localhost:5000/'+ $scope.productId +'/tests/corr' + $scope.corrId + '/build/' + $scope.selectedBuild;
            $http.get(testapi).then(
                function(response){
                    $scope.tests = response.data;
                    console.log($scope.tests)
                    $scope.selectedTest = $scope.tests[0];
            } );
    }
});